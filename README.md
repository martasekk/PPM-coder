<section>
  <h2>Features</h2>
  <ul>
    <li>A Python implementation of Prediction by Partial Matching (PPM) compression with arithmetic coding.</li>
    <li>This tool can encode and decode binary or text files using adaptive context modeling.</li>
    <li>Works on any binary file (text, images, etc.)</li>
    
  </ul>
</section>

<h3>Disclaimer</h3>
<ul>
  <li>This is my personal project to better understand compression methods</li>
  <li>Project is not optimized for real world usage</li>
</ul>

<section>
  <h2>Usage</h2>

  <h3>Encode</h3>
  <pre><code>python ppmcoder.py encode &lt;input_file&gt; &lt;output_file&gt; [order]</code></pre>
  <p class="muted">Example:</p>
  <pre><code>python ppmcoder.py encode test.txt compressed.bin 3</code></pre>

  <h3>Decode</h3>
  <pre><code>python ppmcoder.py decode &lt;input_file&gt; &lt;output_file&gt; [order]</code></pre>
  <p class="muted">Example:</p>
  <pre><code>python ppmcoder.py decode compressed.bin restored.txt 3</code></pre>
</section>

<section>
  <h2>Command summary</h2>
  <table>
    <thead>
      <tr><th>Argument</th><th>Description</th><th>Default</th></tr>
    </thead>
    <tbody>
      <tr><td><code>encode/decode</code></td><td>Mode of operation</td><td>—</td></tr>
      <tr><td><code>&lt;input_file&gt;</code></td><td>Path to the input file</td><td>—</td></tr>
      <tr><td><code>&lt;output_file&gt;</code></td><td>Path to the output file</td><td>—</td></tr>
      <tr><td><code>[order]</code></td><td>PPM model order (how many previous bytes are used as context)</td><td><code>3</code></td></tr>
    </tbody>
  </table>
</section>

<section>
  <h2>Requirements</h2>
  <ul>
    <li>Python 3.8+</li>
    <li><code>bitarray</code> Python package</li>
  </ul>
  <pre><code>pip install bitarray</code></pre>
</section>

<section>
  <h2>Design notes</h2>
  <ul>
    <li>The compressed file stores the original uncompressed length in the first 4 bytes (big-endian).</li>
    <li>Always use the <em>same</em> PPM order for encoding and decoding.</li>
    <li>This implementation is intended as a reference/educational project — it is not optimized for performance or very large files.</li>
  </ul>
