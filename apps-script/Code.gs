const EXPECTED_TOKEN = 'REPLACE_ME_WITH_THE_SAME_TOKEN_YOU_USE_IN_GITHUB_SECRETS';
const RECIPIENT = 'jackson.p.barnes@outlook.com';

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({ ok: false, error: 'Missing request body' }, 400);
    }

    const payload = JSON.parse(e.postData.contents);
    if (payload.token !== EXPECTED_TOKEN) {
      return jsonResponse({ ok: false, error: 'Unauthorized' }, 401);
    }

    const subject = payload.subject || 'Daily Brief';
    const htmlBody = payload.html || '<p>No content.</p>';
    const textBody = payload.text || 'No content.';

    MailApp.sendEmail({
      to: RECIPIENT,
      subject: subject,
      body: textBody,
      htmlBody: htmlBody,
      name: 'Daily Brief Bot'
    });

    return jsonResponse({ ok: true });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error) }, 500);
  }
}

function jsonResponse(data, statusCode) {
  const output = ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);

  // Apps Script does not let us set arbitrary HTTP status codes directly in ContentService.
  // The JSON body is enough for this simple webhook.
  return output;
}
