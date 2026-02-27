const fs = require("fs");
const os = require("os");
const path = require("path");
const test = require("node:test");
const assert = require("node:assert/strict");

const helper = require("../scripts/github_pr_comment");

function makeGithub(comments) {
  const state = {
    comments,
    updates: [],
    creates: [],
    deletes: [],
  };

  return {
    state,
    paginate: async () => state.comments,
    rest: {
      issues: {
        updateComment: async (payload) => {
          state.updates.push(payload);
        },
        createComment: async (payload) => {
          state.creates.push(payload);
        },
        deleteComment: async (payload) => {
          state.deletes.push(payload);
        },
      },
    },
  };
}

function makeContext() {
  return {
    repo: { owner: "octo", repo: "bench" },
    payload: { pull_request: { number: 3 } },
  };
}

test("loadHistory extracts embedded history payload", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "bench-history-"));
  const historyPath = path.join(tempDir, "history.json");
  const github = makeGithub([
    {
      body: '<!-- rust-pr-bench -->\n<!-- criterion-history: {"history":[{"commit":"abc1234"}]} -->',
    },
  ]);

  await helper.loadHistory({
    github,
    context: makeContext(),
    core: { info() {} },
    historyPath,
    historyKey: "criterion-history",
    markers: ["<!-- rust-pr-bench -->", "<!-- criterion-bench -->"],
  });

  assert.deepEqual(JSON.parse(fs.readFileSync(historyPath, "utf8")), {
    history: [{ commit: "abc1234" }],
  });
});

test("loadHistory ignores malformed history payloads", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "bench-history-"));
  const historyPath = path.join(tempDir, "history.json");
  const github = makeGithub([
    {
      body: "<!-- rust-pr-bench -->\n<!-- criterion-history: not-json -->",
    },
  ]);

  await helper.loadHistory({
    github,
    context: makeContext(),
    core: { info() {} },
    historyPath,
    historyKey: "criterion-history",
    markers: ["<!-- rust-pr-bench -->"],
  });

  assert.equal(fs.existsSync(historyPath), false);
});

test("upsertReport updates an existing matching comment", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "bench-report-"));
  const reportPath = path.join(tempDir, "report.md");
  fs.writeFileSync(reportPath, "# report\n");
  const github = makeGithub([{ id: 11, body: "<!-- criterion-bench -->\nold" }]);

  await helper.upsertReport({
    github,
    context: makeContext(),
    reportPath,
    primaryMarker: "<!-- criterion-bench -->",
    markers: ["<!-- criterion-bench -->"],
    deleteExtras: false,
  });

  assert.equal(github.state.updates.length, 1);
  assert.equal(github.state.creates.length, 0);
  assert.match(github.state.updates[0].body, /# report/);
});

test("upsertReport deletes extra legacy comments in consolidated mode", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "bench-report-"));
  const reportPath = path.join(tempDir, "report.md");
  fs.writeFileSync(reportPath, "# combined report\n");
  const github = makeGithub([
    { id: 10, body: "<!-- rust-pr-bench -->\nold" },
    { id: 11, body: "<!-- iai-callgrind-bench -->\nold" },
    { id: 12, body: "<!-- criterion-bench -->\nold" },
  ]);

  await helper.upsertReport({
    github,
    context: makeContext(),
    reportPath,
    primaryMarker: "<!-- rust-pr-bench -->",
    markers: [
      "<!-- rust-pr-bench -->",
      "<!-- iai-callgrind-bench -->",
      "<!-- criterion-bench -->",
    ],
    deleteExtras: true,
  });

  assert.equal(github.state.updates.length, 1);
  assert.equal(github.state.deletes.length, 2);
  assert.deepEqual(
    github.state.deletes.map((item) => item.comment_id).sort(),
    [11, 12],
  );
});

test("upsertReport is a no-op outside pull request context", async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "bench-report-"));
  const reportPath = path.join(tempDir, "report.md");
  fs.writeFileSync(reportPath, "# report\n");
  const github = makeGithub([]);

  await helper.upsertReport({
    github,
    context: { repo: { owner: "octo", repo: "bench" }, payload: {} },
    reportPath,
    primaryMarker: "<!-- criterion-bench -->",
    markers: ["<!-- criterion-bench -->"],
    deleteExtras: false,
  });

  assert.equal(github.state.updates.length, 0);
  assert.equal(github.state.creates.length, 0);
});
