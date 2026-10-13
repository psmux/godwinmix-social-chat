// Seal a value with the panel's own code, for tests/test_seal.py.
//   node tests/seal_node.mjs <public hex> <text>
import { seal, sha256 } from "../ui/seal.js";

const [pub, text] = process.argv.slice(2);
if (pub === "--sha") {
  process.stdout.write(Buffer.from(sha256(new TextEncoder().encode(text))).toString("hex"));
} else {
  process.stdout.write(JSON.stringify(seal(pub, text)));
}
