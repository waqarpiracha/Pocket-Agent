/**
 * ============================================================================
 * GOOGLE DRIVE ROBOT (google_drive_robot.gs)
 * Zero-Server Backend for Waqar-SuperAgent Android App
 * ============================================================================
 * 
 * Capabilities:
 * 1. Second Brain Knowledge Hub (Search and Append to Google Docs)
 * 2. Google Drive Video Browser (Scan & list all .mp4/video files in Drive)
 * 3. Video Publishing Queue (Google Sheet tracking)
 * 4. Direct Native Upload to YouTube via Advanced YouTube Service
 * 5. Bridges for Instagram Reels & TikTok Content Posting APIs
 */

var SECOND_BRAIN_DOC_NAME = "AI_Second_Brain_Master";
var VIDEO_QUEUE_SHEET_NAME = "Video_Publishing_Queue";
var VIDEO_FOLDER_NAME = "PocketAgent_Videos";

function doGet(e) {
  try {
    var action = (e && e.parameter && e.parameter.action) ? e.parameter.action : "status";
    
    if (action === "status") {
      return jsonResponse({
        status: "online",
        service: "Waqar-SuperAgent Google Drive Robot",
        timestamp: new Date().toISOString()
      });
    }
    
    // Browse & list videos sitting directly in Google Drive
    if (action === "list_drive_videos" || action === "list_videos") {
      var folder = (e.parameter.folder || "").trim();
      var videos = listVideosInDrive(folder);
      return jsonResponse({ status: "success", count: videos.length, videos: videos });
    }
    
    // Read video queue sheet
    if (action === "get_video_queue") {
      var queue = getVideoQueue();
      return jsonResponse({ status: "success", count: queue.length, queue: queue });
    }
    
    // Query Second Brain doc
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

function doPost(e) {
  try {
    var rawData = e.postData ? e.postData.contents : "{}";
    var payload = JSON.parse(rawData);
    var action = payload.action || "unknown";
    
    // Save to Second Brain
    if (action === "save" || action === "save_second_brain") {
      var topic = payload.topic || "General";
      var content = payload.content || "";
      var saved = appendToSecondBrain(topic, content);
      return jsonResponse({ status: "success", message: saved });
    }
    
    // Update queue metadata
    if (action === "update_video_metadata") {
      var filename = payload.filename;
      var title = payload.title;
      var description = payload.description;
      var hashtags = payload.hashtags;
      var account = payload.account || "Waqar Analytics";
      var updated = updateVideoRow(filename, account, title, description, hashtags);
      return jsonResponse({ status: "success", message: updated });
    }
    
    // Direct publish video to YouTube and other platforms
    if (action === "publish_video") {
      var filename = payload.filename;
      var account = payload.account || "Waqar Analytics";
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

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ============================================================================
// 1. GOOGLE DRIVE VIDEO BROWSER
// ============================================================================

/**
 * Lists all video files sitting inside user's Google Drive
 */
function listVideosInDrive(folderName) {
  var videoList = [];
  var files;
  
  if (folderName && folderName !== "all" && folderName !== "root") {
    var folders = DriveApp.getFoldersByName(folderName);
    if (folders.hasNext()) {
      files = folders.next().getFiles();
    } else {
      files = DriveApp.searchFiles("mimeType contains 'video/' and trashed = false");
    }
  } else {
    files = DriveApp.searchFiles("mimeType contains 'video/' and trashed = false");
  }
  
  while (files && files.hasNext() && videoList.length < 60) {
    var f = files.next();
    var name = f.getName();
    if (name.match(/\.(mp4|mov|avi|mkv|webm)$/i) || (f.getMimeType() && f.getMimeType().indexOf("video/") !== -1)) {
      videoList.push({
        id: f.getId(),
        name: name,
        sizeMb: (f.getSize() / (1024 * 1024)).toFixed(2),
        updatedAt: Utilities.formatDate(f.getLastUpdated(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm"),
        url: f.getUrl()
      });
    }
  }
  return videoList;
}

// ============================================================================
// 2. SECOND BRAIN FUNCTIONS
// ============================================================================

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
      if (matches.length >= 8) break;
    }
  }
  return matches.length > 0 ? matches.join("\n\n") : "No matching notes found for '" + keyword + "'.";
}

function getOrCreateSecondBrainDoc() {
  var files = DriveApp.getFilesByName(SECOND_BRAIN_DOC_NAME);
  if (files.hasNext()) return DocumentApp.openById(files.next().getId());
  var newDoc = DocumentApp.create(SECOND_BRAIN_DOC_NAME);
  newDoc.getBody().appendParagraph("=== WAQAR PIRACHA - AI SECOND BRAIN KNOWLEDGE VAULT ===");
  newDoc.saveAndClose();
  return newDoc;
}

// ============================================================================
// 3. VIDEO QUEUE SPREADSHEET FUNCTIONS
// ============================================================================

function getVideoQueue() {
  var sheet = getOrCreateVideoQueueSheet();
  var data = sheet.getDataRange().getValues();
  var queue = [];
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[0]) {
      queue.push({
        rowIndex: i + 1,
        filename: String(row[0]).trim(),
        account: String(row[1] || "Waqar Analytics").trim(),
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
  if (!found) sheet.appendRow([filename, account, title, description, hashtags, "Ready", timestamp]);
  return "Updated metadata for " + filename;
}

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
    sheet.getRange("A1:G1").setFontWeight("bold").setBackground("#0F172A").setFontColor("#10B981");
  }
  return ss.getSheetByName("Queue") || ss.getActiveSheet();
}

// ============================================================================
// 4. VIDEO PUBLISHING ENGINE (YOUTUBE, INSTAGRAM, TIKTOK)
// ============================================================================

function executePublishVideo(filename, account, title, description, hashtags, platforms) {
  var videoFiles = DriveApp.getFilesByName(filename);
  if (!videoFiles.hasNext()) {
    return {
      status: "error",
      message: "Video file '" + filename + "' was not found in Google Drive. Make sure it is uploaded to Drive."
    };
  }
  
  var file = videoFiles.next();
  var fullDescription = description + "\n\n" + hashtags;
  var tagsArray = hashtags.replace(/#/g, "").split(/\s+/).filter(function(t) { return t.length > 0; });
  var platformResults = {};
  
  if (platforms.indexOf("youtube") !== -1) {
    try {
      platformResults["youtube"] = uploadToYouTube(file, title, fullDescription, tagsArray);
    } catch (err) {
      platformResults["youtube"] = "Error: " + err.toString();
    }
  }
  
  if (platforms.indexOf("instagram") !== -1) {
    try {
      platformResults["instagram"] = uploadToInstagramReels(file, title + "\n\n" + fullDescription, account);
    } catch (err) {
      platformResults["instagram"] = "Error: " + err.toString();
    }
  }
  
  if (platforms.indexOf("tiktok") !== -1) {
    try {
      platformResults["tiktok"] = uploadToTikTok(file, title + " " + hashtags, account);
    } catch (err) {
      platformResults["tiktok"] = "Error: " + err.toString();
    }
  }
  
  markVideoStatus(filename, "Published ✅");
  
  return {
    status: "success",
    filename: filename,
    account: account,
    platforms: platformResults,
    message: "Video '" + filename + "' published via Google Drive Robot!"
  };
}

function uploadToYouTube(driveFile, title, description, tags) {
  if (typeof YouTube === "undefined") {
    return "Notice: Please add 'YouTube Data API v3' in Google Apps Script Services (+) sidebar. Verified file: " + driveFile.getName();
  }
  
  var videoResource = {
    snippet: {
      title: title,
      description: description,
      tags: tags,
      categoryId: "28"
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

function uploadToInstagramReels(driveFile, caption, accountName) {
  var props = PropertiesService.getScriptProperties();
  var igUserId = props.getProperty("IG_USER_ID_" + accountName.replace(/\s+/g, "_")) || props.getProperty("IG_USER_ID");
  var igToken = props.getProperty("IG_ACCESS_TOKEN_" + accountName.replace(/\s+/g, "_")) || props.getProperty("IG_ACCESS_TOKEN");
  
  if (!igUserId || !igToken) {
    return "Notice: Set 'IG_USER_ID' and 'IG_ACCESS_TOKEN' in Script Properties to auto-push Reels for " + accountName;
  }
  
  var fileUrl = driveFile.getDownloadUrl();
  var containerUrl = "https://graph.facebook.com/v19.0/" + igUserId + "/media";
  var payload = { media_type: "REELS", video_url: fileUrl, caption: caption, access_token: igToken };
  var resp = UrlFetchApp.fetch(containerUrl, { method: "post", payload: payload, muteHttpExceptions: true });
  var json = JSON.parse(resp.getContentText());
  
  if (json.id) {
    var pubUrl = "https://graph.facebook.com/v19.0/" + igUserId + "/media_publish";
    UrlFetchApp.fetch(pubUrl, { method: "post", payload: { creation_id: json.id, access_token: igToken }, muteHttpExceptions: true });
    return "Published to Instagram (ID: " + json.id + ")";
  }
  return "IG Error: " + resp.getContentText();
}

function uploadToTikTok(driveFile, title, accountName) {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty("TIKTOK_ACCESS_TOKEN_" + accountName.replace(/\s+/g, "_")) || props.getProperty("TIKTOK_ACCESS_TOKEN");
  if (!token) return "Notice: Set 'TIKTOK_ACCESS_TOKEN' in Script Properties for " + accountName;
  
  var initUrl = "https://open.tiktokapis.com/v2/post/publish/video/init/";
  var payload = {
    post_info: { title: title, privacy_level: "PUBLIC_TO_EVERYONE" },
    source_info: { source: "FILE_UPLOAD", video_size: driveFile.getSize(), chunk_size: driveFile.getSize(), total_chunk_count: 1 }
  };
  var resp = UrlFetchApp.fetch(initUrl, {
    method: "post", contentType: "application/json",
    headers: { "Authorization": "Bearer " + token },
    payload: JSON.stringify(payload), muteHttpExceptions: true
  });
  return "TikTok API Init: " + resp.getContentText().slice(0, 150);
}
