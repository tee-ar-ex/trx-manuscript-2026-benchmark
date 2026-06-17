import { loadData } from './js/utils.js';
async function test() {
  try {
    const data = await loadData('/home/local/USHERBROOKE/rhef1902/Libraries/trx/trx_benchmark_04_2026_small/f32_w_metadata.trk');
    console.log("Success! Points:", data.pts.length);
  } catch (e) {
    console.error("FAIL:", e.stack);
  }
}
test();
