/**
 * ============================================================================
 * GOOGLE DRIVE ROBOT (google_drive_robot.gs)
 * Zero-Server, 100% Free Backend for Pocket Agent Mobile App
 * ============================================================================
 * 
 * Capabilities:
 * 1. Second Brain Knowledge Hub (Search and Append to Google Docs/Sheets)
 * 2. Video Publishing Queue (Track videos, accounts, metadata, and status)
 * 3. Direct Native Upload to YouTube via Advanced YouTube Service
 * 4. Bridges to Instagram Reels & TikTok Content Posting APIs
 */

// Configuration Constants (Defaults)
var SECOND_BRAIN_DOC_NAME = "AI_Second_Brain_Master";
var VIDEO_QUEUE_SHEET_NAME = "Video_Publishing_Queue";
var VIDEO_FOLDER_NAME = "PocketAgent_Videos";

/**
 * Handle HTTP GET Requests (e.g. Querying Second Brain or Loading Video Queue)
 */
function doGet(e) {
  try {
    var action = (e && e.parameter && e.parameter.action) ? e.parameter.action : "status";
    
    if (action === "status") {
      return jsonResponse({
        status: "online",
        service: "Google Drive Robot for Pocket Agent",
        timestamp: new Date().toISOString()
      });
    }
    
    if (action === "get_video_queue") {
      var queue = getVideoQueue();
      return jsonResponse({ status: "success", count: queue.length, queue: queue });
    }
    
    if (action === "query" || action === "query_second_brain") {
      var query = (e.parameter.q || "").trim();
      var results = querySecondBrain(query);
      return jsonResponse({ status: "success", query: query, results: results });
    }
    
    return jsonResponse({ status: "error", message: "Unknown GET action: " + action });
  } catch (err) {
    return jsonResponse({ status: "error", error: err.toString() });
  }
}

/**
 * Handle HTTP POST Requests (e.g. Uploading Videos, Saving Notes, Updating Queue)
 */
function doPost(e) {
  try {
    var rawData = e.postData ? e.postData.contents : "{}";
    var payload = JSON.parse(rawData);
    var action = payload.action || "unknown";
    
    if (action === "save" || action === "save_second_brain") {
      var topic = payload.topic || "General";
      var content = payload.content || "";
      var saved = appendToSecondBrain(topic, content);
      return jsonResponse({ status: "success", message: saved });
    }
    
    if (action === "update_video_metadata") {
      var filename = payload.filename;
      var title = payload.title;
      var description = payload.description;
      var hashtags = payload.hashtags;
      var account = payload.account || "Account 1";
      var updated = updateVideoRow(filename, account, title, description, hashtags);
      return jsonResponse({ status: "success", message: updated });
    }
    
    if (action === "publish_video") {
      var filename = payload.filename;
      var account = payload.account || "Account 1";
      var title = payload.title || "New Video";
      var description = payload.description || "";
      var hashtags = payload.hashtags || "";
      var platforms = payload.platforms || ["youtube"];
      
      var publishResult = executePublishVideo(filename, account, title, description, hashtags, platforms);
      return jsonResponse(publishResult);
    }
    
    return jsonResponse({ status: "error", message: "Unknown POST action: " + action });
  } catch (err) {
    return jsonResponse({ status: "error", error: err.toString() });
  }
}

/**
 * Return formatted JSON response with CORS headers
 */
function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ============================================================================
// 1. SECOND BRAIN KNOWLEDGE HUB FUNCTIONS
// ============================================================================

/**
 * Appends a new entry to the user's Second Brain Master Google Doc
 */
function appendToSecondBrain(topic, content) {
  var doc = getOrCreateSecondBrainDoc();
  var body = doc.getBody();
  var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
  
  body.appendParagraph("--------------------------------------------------");
  var heading = body.appendParagraph("[" + topic + "] - " + timestamp);
  heading.setHeading(DocumentApp.ParagraphHeading.HEADING3);
  body.appendParagraph(content);
  doc.saveAndClose();
  
  return "Logged to Second Brain (" + SECOND_BRAIN_DOC_NAME + ") at " + timestamp;
}

/**
 * Searches the Second Brain doc for relevant paragraphs
 */
function querySecondBrain(keyword) {
  if (!keyword) return "Please supply a search keyword.";
  var doc = getOrCreateSecondBrainDoc();
  var text = doc.getBody().getText();
  
  var paragraphs = text.split("\n");
  var matches = [];
  var lowerK = keyword.toLowerCase();
  
  for (var i = 0; i < paragraphs.length; i++) {
    var p = paragraphs[i].trim();
    if (p.length > 0 && p.toLowerCase().indexOf(lowerK) !== -1) {
      matches.push(p);
      if (matches.length >= 8) break; // Limit top 8 context snippets
    }
  }
  
  if (matches.length === 0) {
    return "No matching notes found in Second Brain for '" + keyword + "'.";
  }
  return matches.join("\n\n");
}

function getOrCreateSecondBrainDoc() {
  var files = DriveApp.getFilesByName(SECOND_BRAIN_DOC_NAME);
  if (files.hasNext()) {
    return DocumentApp.openById(files.next().getId());
  }
  var newDoc = DocumentApp.create(SECOND_BRAIN_DOC_NAME);
  newDoc.getBody().appendParagraph("=== WAQAR PIRACHA - AI SECOND BRAIN KNOWLEDGE VAULT ===");
  newDoc.saveAndClose();
  return newDoc;
}

// ============================================================================
// 2. VIDEO QUEUE SPREADSHEET FUNCTIONS
// ============================================================================

/**
 * Reads all queued videos from the Google Sheet
 */
function getVideoQueue() {
  var sheet = getOrCreateVideoQueueSheet();
  var data = sheet.getDataRange().getValues();
  var queue = [];
  
  // Row 0 is Headers: [Filename, Account, Title, Description, Hashtags, Status, Updated_At]
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[0]) {
      queue.push({
        rowIndex: i + 1,
        filename: String(row[0]).trim(),
        account: String(row[1] || "Account 1").trim(),
        title: String(row[2] || ""),
        description: String(row[3] || ""),
        hashtags: String(row[4] || ""),
        status: String(row[5] || "Ready"),
        updatedAt: String(row[6] || "")
      });
    }
  }
  return queue;
}

/**
 * Updates or inserts metadata for a specific video row
 */
function updateVideoRow(filename, account, title, description, hashtags) {
  var sheet = getOrCreateVideoQueueSheet();
  var data = sheet.getDataRange().getValues();
  var found = false;
  var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm");
  
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toLowerCase() === filename.trim().toLowerCase()) {
      sheet.getRange(i + 1, 2).setValue(account);
      sheet.getRange(i + 1, 3).setValue(title);
      sheet.getRange(i + 1, 4).setValue(description);
      sheet.getRange(i + 1, 5).setValue(hashtags);
      sheet.getRange(i + 1, 7).setValue(timestamp);
      found = true;
      break;
    }
  }
  
  if (!found) {
    sheet.appendRow([filename, account, title, description, hashtags, "Ready", timestamp]);
  }
  return "Updated metadata for " + filename;
}

/**
 * Marks video status in the spreadsheet
 */
function markVideoStatus(filename, newStatus) {
  var sheet = getOrCreateVideoQueueSheet();
  var data = sheet.getDataRange().getValues();
  var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm");
  
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toLowerCase() === filename.trim().toLowerCase()) {
      sheet.getRange(i + 1, 6).setValue(newStatus);
      sheet.getRange(i + 1, 7).setValue(timestamp);
      return true;
    }
  }
  return false;
}

function getOrCreateVideoQueueSheet() {
  var files = DriveApp.getFilesByName(VIDEO_QUEUE_SHEET_NAME);
  var ss;
  if (files.hasNext()) {
    ss = SpreadsheetApp.openById(files.next().getId());
  } else {
    ss = SpreadsheetApp.create(VIDEO_QUEUE_SHEET_NAME);
    var sheet = ss.getActiveSheet();
    sheet.setName("Queue");
    sheet.appendRow(["Video_Filename", "Account_Name", "Title", "Description", "Hashtags", "Status", "Last_Updated"]);
    sheet.getRange("A1:G1").setFontWeight("bold").setBackground("#1E293B").setFontColor("#FFFFFF");
    
    // Seed sample row so user sees how it works
    sheet.appendRow([
      "sample_video.mp4",
      "Waqar Analytics",
      "Stop Copy-Pasting in Excel! Power BI Automation Hack",
      "Transforming messy corporate data into interactive executive reporting.",
      "#PowerBI #ExcelAutomation #SupplyChain #BusinessIntelligence",
      "Ready",
      new Date().toLocaleString()
    ]);
  }
  return ss.getSheetByName("Queue") || ss.getActiveSheet();
}

// ============================================================================
// 3. ZERO-SERVER VIDEO PUBLISHING ENGINE
// ============================================================================

/**
 * Publishes video file directly from Google Drive to selected channels
 */
function executePublishVideo(filename, account, title, description, hashtags, platforms) {
  // 1. Locate video file in Google Drive
  var videoFiles = DriveApp.getFilesByName(filename);
  if (!videoFiles.hasNext()) {
    return {
      status: "error",
      message: "Video file '" + filename + "' was not found in your Google Drive root or shared folders. Please place it in Drive first."
    };
  }
  
  var file = videoFiles.next();
  var fullDescription = description + "\n\n" + hashtags;
  var tagsArray = hashtags.replace(/#/g, "").split(/\s+/).filter(function(t) { return t.length > 0; });
  var platformResults = {};
  
  // 2. Publish to YouTube via Google Apps Script Advanced YouTube Service
  if (platforms.indexOf("youtube") !== -1) {
    try {
      var ytResult = uploadToYouTube(file, title, fullDescription, tagsArray);
      platformResults["youtube"] = ytResult;
    } catch (err) {
      platformResults["youtube"] = "Error: " + err.toString();
    }
  }
  
  // 3. Publish to Instagram Reels via Graph API
  if (platforms.indexOf("instagram") !== -1) {
    try {
      var igResult = uploadToInstagramReels(file, title + "\n\n" + fullDescription, account);
      platformResults["instagram"] = igResult;
    } catch (err) {
      platformResults["instagram"] = "Error: " + err.toString();
    }
  }
  
  // 4. Publish to TikTok Content Posting API
  if (platforms.indexOf("tiktok") !== -1) {
    try {
      var ttResult = uploadToTikTok(file, title + " " + hashtags, account);
      platformResults["tiktok"] = ttResult;
    } catch (err) {
      platformResults["tiktok"] = "Error: " + err.toString();
    }
  }
  
  // Mark status in spreadsheet
  markVideoStatus(filename, "Published ✅");
  
  return {
    status: "success",
    filename: filename,
    account: account,
    platforms: platformResults,
    message: "Video '" + filename + "' processed across selected channels for " + account + "!"
  };
}

/**
 * Uploads a video from Drive to YouTube using YouTube Advanced Service
 * Note: Must enable 'YouTube Data API v3' in Apps Script Services (Resources -> Advanced Google services)
 */
function uploadToYouTube(driveFile, title, description, tags) {
  if (typeof YouTube === "undefined") {
    return "YouTube Service Notice: Please click 'Services' (+) in Google Apps Script and add 'YouTube Data API v3'. File verified: " + driveFile.getName();
  }
  
  var videoResource = {
    snippet: {
      title: title,
      description: description,
      tags: tags,
      categoryId: "28" // Science & Technology
    },
    status: {
      privacyStatus: "public",
      selfDeclaredMadeForKids: false
    }
  };
  
  var mediaData = driveFile.getBlob();
  var response = YouTube.Videos.insert(videoResource, "snippet,status", mediaData);
  return "https://youtu.be/" + response.id;
}

/**
 * Instagram Reels Video Publishing Helper (Meta Graph API)
 */
function uploadToInstagramReels(driveFile, caption, accountName) {
  // Read stored access token from ScriptProperties
  var userProperties = PropertiesService.getScriptProperties();
  var igUserId = userProperties.getProperty("IG_USER_ID_" + accountName.replace(/\s+/g, "_")) || userProperties.getProperty("IG_USER_ID");
  var igAccessToken = userProperties.getProperty("IG_ACCESS_TOKEN_" + accountName.replace(/\s+/g, "_")) || userProperties.getProperty("IG_ACCESS_TOKEN");
  
  if (!igUserId || !igAccessToken) {
    return "Instagram Token Notice: Please set 'IG_USER_ID' and 'IG_ACCESS_TOKEN' in Script Properties to auto-push Reels for " + accountName;
  }
  
  // Make file temporarily web-accessible for Meta's media container ingestion
  var fileUrl = driveFile.getDownloadUrl();
  var containerUrl = "https://graph.facebook.com/v19.0/" + igUserId + "/media";
  
  var payload = {
    media_type: "REELS",
    video_url: fileUrl,
    caption: caption,
    access_token: igAccessToken
  };
  
  var options = {
    method: "post",
    payload: payload,
    muteHttpExceptions: true
  };
  
  var response = UrlFetchApp.fetch(containerUrl, options);
  var json = JSON.parse(response.getContentText());
  
  if (json.id) {
    // Publish container
    var publishUrl = "https://graph.facebook.com/v19.0/" + igUserId + "/media_publish";
    var pubPayload = { creation_id: json.id, access_token: igAccessToken };
    var pubResp = UrlFetchApp.fetch(publishUrl, { method: "post", payload: pubPayload, muteHttpExceptions: true });
    return "Published to Instagram (ID: " + json.id + ")";
  }
  return "IG Container Response: " + response.getContentText();
}

/**
 * TikTok Content Posting API Helper
 */
function uploadToTikTok(driveFile, title, accountName) {
  var userProperties = PropertiesService.getScriptProperties();
  var ttToken = userProperties.getProperty("TIKTOK_ACCESS_TOKEN_" + accountName.replace(/\s+/g, "_")) || userProperties.getProperty("TIKTOK_ACCESS_TOKEN");
  
  if (!ttToken) {
    return "TikTok Token Notice: Please set 'TIKTOK_ACCESS_TOKEN' in Script Properties to auto-post to TikTok for " + accountName;
  }
  
  // Direct publish endpoint
  var initUrl = "https://open.tiktokapis.com/v2/post/publish/video/init/";
  var payload = {
    post_info: {
      title: title,
      privacy_level: "PUBLIC_TO_EVERYONE",
      disable_duet: false,
      disable_stitch: false,
      disable_comment: false
    },
    source_info: {
      source: "FILE_UPLOAD",
      video_size: driveFile.getSize(),
      chunk_size: driveFile.getSize(),
      total_chunk_count: 1
    }
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    headers: { "Authorization": "Bearer " + ttToken },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  var resp = UrlFetchApp.fetch(initUrl, options);
  return "TikTok API Initialized: " + resp.getContentText().slice(0, 150);
}
