const RESULTS_SHEET_NAME = 'Results';
const EXPECTED_ROW_COUNT = 20;
const MAX_ROWS_PER_SUBMISSION = 100;

function doGet() {
  return jsonOutput_({
    ok: true,
    service: 'UserStudy_traj result collector'
  });
}

function doPost(e) {
  const lock = LockService.getScriptLock();

  try {
    if (!e || !e.postData || !e.postData.contents) {
      throw new Error('Missing request body.');
    }

    const payload = JSON.parse(e.postData.contents);
    validatePayload_(payload);

    lock.waitLock(30000);

    const sheet = getOrCreateResultsSheet_();
    const submissionIdColumn = 3;
    const existingSubmission = sheet
      .getRange(2, submissionIdColumn, Math.max(sheet.getLastRow() - 1, 1), 1)
      .createTextFinder(payload.submissionId)
      .matchEntireCell(true)
      .findNext();

    if (existingSubmission) {
      return jsonOutput_({
        ok: true,
        duplicate: true,
        submissionId: payload.submissionId
      });
    }

    const receivedAt = new Date();
    const values = payload.rows.map(row => [
      receivedAt,
      payload.participantId,
      payload.submissionId,
      row.scene,
      row.method,
      Number(row.trajectory),
      Number(row.quality),
      Number(row.rhythm),
      Number(row.footContact),
      row.timestamp
    ]);

    sheet
      .getRange(sheet.getLastRow() + 1, 1, values.length, values[0].length)
      .setValues(values);

    SpreadsheetApp.flush();

    return jsonOutput_({
      ok: true,
      duplicate: false,
      submissionId: payload.submissionId,
      rowsWritten: values.length
    });
  } catch (error) {
    console.error(error);
    return jsonOutput_({
      ok: false,
      error: String(error && error.message ? error.message : error)
    });
  } finally {
    if (lock.hasLock()) {
      lock.releaseLock();
    }
  }
}

function getOrCreateResultsSheet_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName(RESULTS_SHEET_NAME);

  if (!sheet) {
    sheet = spreadsheet.insertSheet(RESULTS_SHEET_NAME);
  }

  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      'receivedAt',
      'participantId',
      'submissionId',
      'scene',
      'method',
      'trajectory',
      'quality',
      'rhythm',
      'footContact',
      'clientTimestamp'
    ]);
    sheet.setFrozenRows(1);
  }

  return sheet;
}

function validatePayload_(payload) {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Invalid payload.');
  }

  validateId_(payload.participantId, 'participantId');
  validateId_(payload.submissionId, 'submissionId');

  if (!Array.isArray(payload.rows)) {
    throw new Error('rows must be an array.');
  }

  if (payload.rows.length !== EXPECTED_ROW_COUNT) {
    throw new Error(`Expected ${EXPECTED_ROW_COUNT} rows.`);
  }

  if (payload.rows.length > MAX_ROWS_PER_SUBMISSION) {
    throw new Error('Too many rows.');
  }

  payload.rows.forEach((row, index) => {
    if (!row || typeof row !== 'object') {
      throw new Error(`Invalid row at index ${index}.`);
    }

    validateLabel_(row.scene, `rows[${index}].scene`);
    validateLabel_(row.method, `rows[${index}].method`);
    validateScore_(row.trajectory, `rows[${index}].trajectory`);
    validateScore_(row.quality, `rows[${index}].quality`);
    validateScore_(row.rhythm, `rows[${index}].rhythm`);
    validateScore_(row.footContact, `rows[${index}].footContact`);

    if (typeof row.timestamp !== 'string' || !/^\d{4}-\d{2}-\d{2}T/.test(row.timestamp)) {
      throw new Error(`Invalid timestamp at row ${index}.`);
    }
  });
}

function validateId_(value, fieldName) {
  if (typeof value !== 'string' || !/^[0-9a-f-]{36}$/i.test(value)) {
    throw new Error(`Invalid ${fieldName}.`);
  }
}

function validateLabel_(value, fieldName) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_.-]{1,64}$/.test(value)) {
    throw new Error(`Invalid ${fieldName}.`);
  }
}

function validateScore_(value, fieldName) {
  const score = Number(value);
  if (!Number.isInteger(score) || score < 1 || score > 5) {
    throw new Error(`Invalid ${fieldName}.`);
  }
}

function jsonOutput_(value) {
  return ContentService
    .createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
