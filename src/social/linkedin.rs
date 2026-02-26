//! LinkedIn API client (REST API).

use anyhow::{bail, Result};
use serde_json::json;

/// Maximum character count for a LinkedIn post.
const MAX_BODY_LENGTH: usize = 3000;

/// Maximum images in a multi-image carousel.
const MAX_IMAGES: usize = 20;

/// LinkedIn visibility values.
pub fn map_visibility(visibility: &str) -> Result<&'static str> {
    match visibility.to_lowercase().as_str() {
        "public" => Ok("PUBLIC"),
        "connections" => Ok("CONNECTIONS"),
        _ => bail!(
            "Invalid LinkedIn visibility '{}'. Valid: public, connections",
            visibility
        ),
    }
}

/// Get the authenticated user's URN via /v2/userinfo.
pub fn get_user_urn(access_token: &str) -> Result<String> {
    let resp = ureq::get("https://api.linkedin.com/v2/userinfo")
        .set("Authorization", &format!("Bearer {}", access_token))
        .call()
        .map_err(|e| anyhow::anyhow!("LinkedIn userinfo request failed: {}", e))?;

    let body: serde_json::Value = resp.into_json()?;
    let sub = body["sub"]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("Missing 'sub' in userinfo response"))?;

    Ok(format!("urn:li:person:{}", sub))
}

/// Initialize an image upload and upload the binary data.
/// Returns the image URN for use in post creation.
pub fn upload_image(access_token: &str, author_urn: &str, image_bytes: &[u8]) -> Result<String> {
    // Step 1: Initialize upload
    let init_payload = json!({
        "initializeUploadRequest": {
            "owner": author_urn
        }
    });

    let init_resp = ureq::post("https://api.linkedin.com/rest/images?action=initializeUpload")
        .set("Authorization", &format!("Bearer {}", access_token))
        .set("LinkedIn-Version", "202401")
        .set("X-Restli-Protocol-Version", "2.0.0")
        .send_json(&init_payload);

    let init_body: serde_json::Value = match init_resp {
        Ok(r) => r.into_json()?,
        Err(ureq::Error::Status(status, resp)) => {
            let body = resp.into_string().unwrap_or_default();
            bail!("LinkedIn image init failed (HTTP {}): {}", status, body);
        }
        Err(e) => bail!("LinkedIn image init request failed: {}", e),
    };

    let upload_url = init_body["value"]["uploadUrl"]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("Missing uploadUrl in image init response"))?;
    let image_urn = init_body["value"]["image"]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("Missing image URN in image init response"))?
        .to_string();

    // Step 2: Upload binary image
    let upload_resp = ureq::put(upload_url)
        .set("Authorization", &format!("Bearer {}", access_token))
        .set("Content-Type", "application/octet-stream")
        .send_bytes(image_bytes);

    match upload_resp {
        Ok(_) => {}
        Err(ureq::Error::Status(status, resp)) => {
            let body = resp.into_string().unwrap_or_default();
            bail!("LinkedIn image upload failed (HTTP {}): {}", status, body);
        }
        Err(e) => bail!("LinkedIn image upload request failed: {}", e),
    }

    Ok(image_urn)
}

/// Create a post on LinkedIn using the REST API.
///
/// `image_urns` controls the post type:
/// - empty: text-only post
/// - 1 image: single image post (`content.media`)
/// - 2+ images: multi-image carousel (`content.multiImage`)
pub fn create_post(
    access_token: &str,
    author_urn: &str,
    body: &str,
    visibility: &str,
    image_urns: &[String],
) -> Result<(String, String)> {
    // Validate body length
    let char_count = body.chars().count();
    if char_count > MAX_BODY_LENGTH {
        bail!(
            "Post body exceeds LinkedIn's {} character limit ({} characters)",
            MAX_BODY_LENGTH,
            char_count
        );
    }

    // Validate image count
    if image_urns.len() > MAX_IMAGES {
        bail!(
            "Too many images ({}) — LinkedIn allows up to {}",
            image_urns.len(),
            MAX_IMAGES
        );
    }

    let li_visibility = map_visibility(visibility)?;

    let mut payload = json!({
        "author": author_urn,
        "commentary": body,
        "visibility": li_visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": false
    });

    // Add image content based on count
    match image_urns.len() {
        0 => {} // text-only, no content field needed
        1 => {
            payload["content"] = json!({
                "media": {
                    "id": image_urns[0]
                }
            });
        }
        _ => {
            let images: Vec<serde_json::Value> = image_urns
                .iter()
                .map(|urn| json!({ "id": urn }))
                .collect();
            payload["content"] = json!({
                "multiImage": {
                    "images": images
                }
            });
        }
    }

    let resp = ureq::post("https://api.linkedin.com/rest/posts")
        .set("Authorization", &format!("Bearer {}", access_token))
        .set("LinkedIn-Version", "202401")
        .set("X-Restli-Protocol-Version", "2.0.0")
        .send_json(&payload);

    match resp {
        Ok(r) => {
            // LinkedIn returns the post ID in the x-restli-id header
            let post_id = r
                .header("x-restli-id")
                .unwrap_or("unknown")
                .to_string();
            let post_url = format!(
                "https://www.linkedin.com/feed/update/{}",
                post_id
            );
            Ok((post_id, post_url))
        }
        Err(ureq::Error::Status(status, resp)) => {
            let body = resp.into_string().unwrap_or_default();
            bail!(
                "LinkedIn API error (HTTP {}): {}",
                status,
                body
            );
        }
        Err(e) => bail!("LinkedIn API request failed: {}", e),
    }
}
