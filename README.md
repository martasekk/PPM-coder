A Python implementation of Prediction by Partial Matching (PPM) compression with arithmetic coding.
This tool can encode and decode binary or text files using adaptive context modeling.

Uses arithmetic range coding for efficient bit-level compression
Works on any binary file (.txt, .bin, .jpg, etc.)
Example usage:
  python ppmcoder.py encode test.txt compressed.bin 2
  python ppmcoder.py decode compressed.bin output.txt 2
Always use the same order when encoding and decoding

Requirements:
pip install bitarray
