from collections import defaultdict
from bitarray import bitarray
import sys
import os

# ============================================================
# constants
# ============================================================


TOTAL_BITS = 32
MAX_RANGE = (1 << TOTAL_BITS) - 1
HALF = 1 << (TOTAL_BITS - 1)
QUARTER = HALF >> 1
MASK = MAX_RANGE - 1
ESC = 256


# ============================================================
# PPM Coder 
# ============================================================
class PPMCoder:
    def __init__(self):
        # Context models
        self.contexts = defaultdict(lambda : defaultdict(int))
        self.order_minus1 = defaultdict(int)
        for i in range(256):  # 0..255
            # order -1: stores cumulative values for symbols
            self.order_minus1[bytes([i])] = 1 

        # History buffer
        self.history = b''
        
        self.order = 0

        # Range and bit counters
        self.low = 0
        self.high = MAX_RANGE
        self.bitqueue = 0

    
    def update_contexts(self, symbol):
        for k in reversed(range(self.order + 1)):
            hst = self.history[-k:] if k > 0 else b''
            self.contexts[hst][symbol] += 1

    def append_to_history(self, symbol):
        if len(self.history) < self.order:
            self.history += symbol
        else:
            self.history = self.history[1:] + symbol

    def make_cumulative(self, ctx):
    # Return cumulative mapping symbol -> cumulative_low (starting at 0),
    # encoder and decoder both use the same function.
        new_freqs = {}
        freqs = self.contexts.get(ctx, {})
        temp = 0
        for key, f in freqs.items():
            new_freqs[key] = temp
            temp += f
            
        # Also add ESC if present (make sure ESC has a cumulative entry if in freqs)
        if ESC in freqs and ESC not in new_freqs:
            new_freqs[ESC] = temp
            temp += freqs[ESC]
        return new_freqs

class Encoder(PPMCoder):

    def __init__(self, order=3):
        super().__init__()
        self.order = order

        # Range and bit counters
        self.low = 0
        self.high = MAX_RANGE
        self.bitqueue = 0

        # I/O streams
        self.output = bitarray()
        self.input_stream = bitarray()
        self.output_stream = 0
        self.index = 0
        self.end = False
        self.code = 0

        self.total = 0
        
    def output_bit(self, bit):
        self.output.append(bit)
        while self.bitqueue > 0:
            self.output.append(not bit)
            self.bitqueue -= 1


    # ========================================================
    # Encoding operations
    # ========================================================

    def update(self, ctx, symbol, order_minus1=False):
    # Update ranges and output bits as needed for the provided symbol within ctx.
    # If order_minus1 is True, use the fixed order-(-1) model.
        if order_minus1:
            total = 256
            l = symbol[0]
            h = l + 1
        else:
            freqs_cum = self.make_cumulative(ctx)
            temp = self.contexts[ctx][symbol]
            total = sum(self.contexts[ctx].values())
            l = freqs_cum.get(symbol, 0)
            h = l + temp

        range = self.high - self.low + 1

        if total == 0:
            # if context is size 0 (empty)
            self.high = self.low + range - 1
        else:
            # update high/low according to standard arithmetic coding formulas
            self.high = self.low + (h * range) // total - 1
            self.low = self.low + (l * range) // total

        # renormalize and output bits
        while True:
            if self.high < HALF:
                # MSB = 0
                self.output_bit(False)

            elif self.low >= HALF:
                # MSB = 1
                self.output_bit(True)
                self.low -= HALF
                self.high -= HALF

            elif QUARTER <= self.low and self.high < 3 * QUARTER:
                # Underflow (E3), count it and shift range
                self.low -= QUARTER
                self.high -= QUARTER
                self.bitqueue += 1

            else:
                break

            # shift left one bit
            self.low <<= 1
            self.high = (self.high << 1) | 1
            self.low &= MAX_RANGE
            self.high &= MAX_RANGE

    def encode(self, input_stream, output_stream, length):    
    # input_stream: a file-like object opened in 'rb' mode
    # output_stream: a file object
    # length: number of bytes to read from input_stream
    # 
    # returns: bitarray of encoded bits
    # 

        self.output_stream = output_stream
        self.high = MAX_RANGE
        self.low = 0
        self.message_len = length
        self.total = 0
        self.history = b''
        self.output.clear()
        self.bitqueue = 0

        while True:
            if length <= self.total:
                break
            self.total += 1

            symbol = input_stream.read(1)

            exit_flag = False

            # Try encoding in decreasing context order
            for k in reversed(range(len(self.history) + 1)):
                hst = self.history[-k:] if k > 0 else b''

                if hst in self.contexts and self.contexts[hst].get(symbol) is not None:
                    self.update(hst, symbol)
                    exit_flag = True
                    break

                # Encode context escape for this hst
                # Use update() with ESC symbol (not order_minus1) and then increment ESC freq
                # (encoder and decoder must update contexts in same order)
                self.update(hst, ESC)
                self.contexts[hst][ESC] += 1

            # If not found in any context, use order -1 model (uniform 0..255)
            if not exit_flag:
                # symbol is a single byte; pass it as integer via bytes to update for order_minus1
                self.update(b'', symbol, True)

            # Now update all contexts with this symbol and append to history
            self.update_contexts(symbol)
            self.append_to_history(symbol)

        # Final flush: emit one bit to identify final interval and flush queued underflow bits.
        # Standard approach: emit bit based on low relative to QUARTER
        self.bitqueue += 1
        if self.low < QUARTER:
            self.output_bit(False)
        else:
            self.output_bit(True)

        return self.output

    # ========================================================
    # Decoding operations
    # ========================================================

class Decoder(PPMCoder):

    def __init__(self, order=3):
        super().__init__()
        self.order = order

        # Range and bit counters
        self.low = 0
        self.high = MAX_RANGE
        self.bitqueue = 0

        # I/O streams
        self.output = bitarray()
        self.input_stream = bitarray()
        self.output_stream = 0
        self.index = 0
        self.end = False
        self.code = 0

        self.total = 0


    def read_bit(self):
    # Read next bit from self.input_stream (bitarray).
        if self.index >= len(self.input_stream):
            # return 0 as padding when no more bits are available
            return 0
        bit = 1 if self.input_stream[self.index] else 0
        self.index += 1
        return bit

    def update_d(self, ctx, symbol, order_minus1=False):  
    # Update function for decoder
    # This mirrors update() behaviour.
        
        if not order_minus1:
            freqs_cum = self.make_cumulative(ctx)
            temp = self.contexts[ctx][symbol]
            total = sum(self.contexts[ctx].values())
            l = freqs_cum.get(symbol, 0)
            h = l + temp
        else:
            temp = 1
            total = 256
            l = symbol[0] if isinstance(symbol, (bytes, bytearray)) else symbol
            h = l + 1

        rng = self.high - self.low + 1

        if total == 0:
            self.high = self.low + rng - 1
        else:
            self.high = self.low + (h * rng) // total - 1
            self.low = self.low + (l * rng) // total

        # renormalize (no bit outputs here; adjust code accordingly)
        while True:
            if self.high < HALF:
                # Nothing to do except shift in next bit
                pass

            elif self.low >= HALF:
                self.low -= HALF
                self.high -= HALF

            elif QUARTER <= self.low and self.high < 3 * QUARTER:
                # E3 underflow case
                self.low -= QUARTER
                self.high -= QUARTER
                self.code -= QUARTER

            else:
                break

            # Shift and read next bit into code
            self.code = ((self.code << 1) | self.read_bit()) & MAX_RANGE
            self.low = (self.low << 1) & MAX_RANGE
            self.high = ((self.high << 1) | 1) & MAX_RANGE

    def read(self, ctx, order_minus1=False):
    # Determine next symbol within given context
        if order_minus1:
            total = 256
        else:
            freqs_cum = self.make_cumulative(ctx)
            total = sum(self.contexts[ctx].values())

        rng = self.high - self.low + 1
        offset = self.code - self.low
        value = ((offset + 1) * total - 1) // rng

        # If using freqs_cum (context), iterate in insertion order (same as encoder)
        if not order_minus1:
            # Find symbol with largest cumulative <= value
            # freqs_cum is symbol -> cumulative_low
            # Create list of (symbol, cumulative_low) in insertion order
            items = list(freqs_cum.items())
            symbol = ESC
            for s, cum in reversed(items):
                if value >= cum:
                    symbol = s
                    break
        else:
            # order -1: symbols 0..255 mapped by their index
            # Value corresponds to the symbol index
            symbol = bytes([value])

        # Update ranges and contexts appropriately
        self.update_d(ctx, symbol, order_minus1)
        if symbol != ESC:
            self.update_contexts(symbol)

        return symbol

    def decode_sym(self):
        # Try contexts from highest order down to order -1 to decode a symbol.
        for k in reversed(range(len(self.history) + 1)):
            hst = self.history[-k:] if k > 0 else b''
            if hst in self.contexts:
                symbol = self.read(hst)
                if symbol != ESC:
                    return symbol
                else: 
                    self.contexts[hst][ESC] += 1
            else:
                # if context unknown, increment ESC and simulate its consumption
                self.contexts[hst][ESC] += 1
        # if all contexts escape, use order -1
        return self.read(b'', True)

    def decode(self, input_stream_bits, output_stream, length):
    # input_stream_bits: bitarray of encoded bits
    # output_stream: file-like object to receive decoded bytes (not strictly used here)
    # length: number of bytes to decode
    # 
    # returns: bytes decoded
    #
        
        self.input_stream = input_stream_bits
        self.index = 0
        self.code = 0

        # Fill code with bits
        for _ in range(TOTAL_BITS):
            self.code = (self.code << 1) | self.read_bit()

        self.contexts = defaultdict(lambda : defaultdict(int))
        self.high = MAX_RANGE
        self.low = 0
        self.total = 0
        self.history = b''
        self.end = False

        while self.total < length:
            self.total += 1
            symbol = self.decode_sym()
            output_stream.write(bytes(symbol))
            self.append_to_history(symbol)

        return output_stream


# ============================================================
# ============================================================

def usage_message():
    print("Usage: python ppmcoder.py <encode/decode> <input_file> <output_file> <order> (if order is not specified, it is set to 3)")
    print("Example: python ppmcoder.py encode test.txt compressed.bin 2")
    print("         python ppmcoder.py decode compressed.bin decompressed.txt 2")
    sys.exit(1)


if __name__ == "__main__":


    if len(sys.argv) > 4:
        ORDER = int(sys.argv[4])
    else:
        ORDER = 3
        
    if len(sys.argv) > 3:
        MODE = sys.argv[1]
        FILE_PATH_INPUT = sys.argv[2]
        FILE_PATH_OUTPUT = sys.argv[3]
    else:
        usage_message()
    
    SIZE_NO_OF_BYTES = 4 # Number of bytes reserved to save the file size
    
    if MODE == "encode":
        coder = Encoder()

        with open(FILE_PATH_INPUT, "rb") as f:
            print(f"Data loaded from {FILE_PATH_INPUT}.")
            length = os.path.getsize(FILE_PATH_INPUT)
            encoded_bits = coder.encode(f, None, length)
            print(f"Compressed into {len(encoded_bits)/8} bytes.")

        with open(FILE_PATH_OUTPUT, "wb") as f:
            f.write(length.to_bytes(SIZE_NO_OF_BYTES, "big"))
            encoded_bits.tofile(f)
            
        print(f"Data saved to {FILE_PATH_OUTPUT}.")
        
    elif MODE == "decode":

        bits = bitarray()
        with open(FILE_PATH_INPUT, "rb") as f:
            length_b = f.read(SIZE_NO_OF_BYTES)
            length = int.from_bytes(length_b, "big")
            bits.fromfile(f)

        print(f"Data loaded from {FILE_PATH_INPUT}.")
        coder = Decoder()
        with open(FILE_PATH_OUTPUT, "wb") as f:
            decoded = coder.decode(bits, f, length)
        print(f"Data decompressed into {length} bytes.")
        print(f"Data saved to {FILE_PATH_OUTPUT}.")
    
    else:
        print("Error: Set the correct mode ")
        usage_message()
