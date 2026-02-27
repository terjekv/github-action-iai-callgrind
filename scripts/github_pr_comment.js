const fs = require("fs");

async function listIssueComments(github, context, issueNumber) {
  return github.paginate(github.rest.issues.listComments, {
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: issueNumber,
  });
}

function logInfo(core, message) {
  if (core && typeof core.info === "function") {
    core.info(message);
  }
}

function findFirstMatchingComment(comments, markers) {
  return comments.find((comment) => {
    if (!comment || !comment.body) {
      return false;
    }
    return markers.some((marker) => comment.body.includes(marker));
  });
}

async function loadHistory({ github, context, core, historyPath, historyKey, markers }) {
  const issueNumber = context.payload?.pull_request?.number;
  if (!issueNumber) {
    return;
  }

  const comments = await listIssueComments(github, context, issueNumber);
  const existing = findFirstMatchingComment(comments, markers);
  if (!existing || !existing.body) {
    return;
  }

  const escapedKey = historyKey.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const historyRegex = new RegExp(`<!-- ${escapedKey}: ([\\s\\S]*?) -->`);
  const match = existing.body.match(historyRegex);
  if (!match) {
    return;
  }

  try {
    const payload = JSON.parse(match[1]);
    fs.writeFileSync(historyPath, JSON.stringify(payload));
  } catch (error) {
    logInfo(core, `Failed to parse history JSON: ${error}`);
  }
}

async function upsertReport({
  github,
  context,
  reportPath,
  primaryMarker,
  markers,
  deleteExtras,
}) {
  const issueNumber = context.payload?.pull_request?.number;
  if (!issueNumber) {
    return;
  }

  const report = fs.readFileSync(reportPath, "utf8");
  const body = `${primaryMarker}\n${report}`;
  const comments = await listIssueComments(github, context, issueNumber);
  const matching = comments.filter(
    (comment) =>
      comment &&
      comment.body &&
      markers.some((marker) => comment.body.includes(marker))
  );

  if (matching.length > 0) {
    const [first, ...rest] = matching;
    await github.rest.issues.updateComment({
      owner: context.repo.owner,
      repo: context.repo.repo,
      comment_id: first.id,
      body,
    });

    if (deleteExtras) {
      for (const extra of rest) {
        await github.rest.issues.deleteComment({
          owner: context.repo.owner,
          repo: context.repo.repo,
          comment_id: extra.id,
        });
      }
    }
    return;
  }

  await github.rest.issues.createComment({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: issueNumber,
    body,
  });
}

module.exports = {
  loadHistory,
  upsertReport,
};
