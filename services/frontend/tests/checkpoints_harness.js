const fs = require("fs");
const vm = require("vm");
const [scenario, script] = process.argv.slice(2);
const options = [];
const status = { textContent: "loading" };
const select = { appendChild: option => options.push(option) };
let requested;
const context = {
  window: { LUMA_CONFIG: { apiBase: "https://backend.example" } },
  document: {
    readyState: "complete",
    getElementById: id => id === "checkpoint" ? select : status,
    createElement: () => ({}),
  },
  fetch: async url => {
    requested = url;
    if (scenario === "offline") throw new Error("offline");
    return {ok: true, json: async () => ({items: scenario === "empty" ? [] : [
      {title: "portrait [111]"}, {title: "<b>landscape</b> [222]"},
    ]})};
  },
};
vm.runInNewContext(fs.readFileSync(script, "utf8"), context);
setImmediate(() => console.log(JSON.stringify({options, status: status.textContent, requested})));
