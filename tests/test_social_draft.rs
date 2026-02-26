//! Draft parsing edge cases (D1–D9).

mod common;

use corky::social::draft::{DraftStatus, SocialDraft, SocialDraftMeta};
use corky::social::platform::Platform;

// D1: Valid draft with all fields
#[test]
fn d1_valid_draft_all_fields() {
    let content = r#"---
platform: linkedin
author: btakita
visibility: public
status: ready
tags:
  - rust
  - ai
---
Hello LinkedIn! This is my post.
"#;

    let draft = SocialDraft::parse(content).unwrap();
    assert_eq!(draft.meta.platform, Platform::LinkedIn);
    assert_eq!(draft.meta.author, "btakita");
    assert_eq!(draft.meta.visibility, "public");
    assert_eq!(draft.meta.status, DraftStatus::Ready);
    assert_eq!(draft.meta.tags, vec!["rust", "ai"]);
    assert!(draft.body.contains("Hello LinkedIn!"));
}

// D2: Missing required field (platform)
#[test]
fn d2_missing_platform() {
    let content = r#"---
author: btakita
---
Some body
"#;

    let result = SocialDraft::parse(content);
    assert!(result.is_err());
    let err = result.unwrap_err().to_string();
    assert!(
        err.contains("platform") || err.contains("missing field"),
        "Expected platform missing error, got: {}",
        err
    );
}

// D3: Missing required field (author)
#[test]
fn d3_missing_author() {
    let content = r#"---
platform: linkedin
---
Some body
"#;

    let result = SocialDraft::parse(content);
    assert!(result.is_err());
    let err = result.unwrap_err().to_string();
    assert!(
        err.contains("author") || err.contains("missing field"),
        "Expected author missing error, got: {}",
        err
    );
}

// D4: Unknown platform
#[test]
fn d4_unknown_platform() {
    let content = r#"---
platform: myspace
author: btakita
---
Some body
"#;

    let result = SocialDraft::parse(content);
    assert!(result.is_err());
    let err = result.unwrap_err().to_string();
    assert!(
        err.contains("unknown variant") || err.contains("myspace"),
        "Expected unknown platform error, got: {}",
        err
    );
}

// D5: Invalid status value
#[test]
fn d5_invalid_status() {
    let content = r#"---
platform: linkedin
author: btakita
status: pending
---
Some body
"#;

    let result = SocialDraft::parse(content);
    assert!(result.is_err());
    let err = result.unwrap_err().to_string();
    assert!(
        err.contains("unknown variant") || err.contains("pending"),
        "Expected invalid status error, got: {}",
        err
    );
}

// D6: No YAML frontmatter delimiters
#[test]
fn d6_no_frontmatter() {
    let content = "Just plain text without frontmatter.";

    let result = SocialDraft::parse(content);
    assert!(result.is_err());
    let err = result.unwrap_err().to_string();
    assert!(
        err.contains("---"),
        "Expected missing delimiter error, got: {}",
        err
    );
}

// D7: Empty body after frontmatter
#[test]
fn d7_empty_body() {
    let content = r#"---
platform: linkedin
author: btakita
---
"#;

    let draft = SocialDraft::parse(content).unwrap();
    assert!(draft.body.is_empty() || draft.body.trim().is_empty());
}

// D8: Render/parse round-trip
#[test]
fn d8_render_parse_roundtrip() {
    let meta = SocialDraftMeta {
        platform: Platform::LinkedIn,
        author: "btakita".to_string(),
        visibility: "public".to_string(),
        status: DraftStatus::Ready,
        tags: vec!["rust".to_string(), "ai".to_string()],
        scheduled_at: None,
        published_at: None,
        post_id: None,
        post_url: None,
        images: vec![],
    };

    let original = SocialDraft::new(meta, "Test body content.\n".to_string());
    let rendered = original.render().unwrap();
    let parsed = SocialDraft::parse(&rendered).unwrap();

    assert_eq!(parsed.meta.platform, original.meta.platform);
    assert_eq!(parsed.meta.author, original.meta.author);
    assert_eq!(parsed.meta.visibility, original.meta.visibility);
    assert_eq!(parsed.meta.status, original.meta.status);
    assert_eq!(parsed.meta.tags, original.meta.tags);
    assert!(parsed.body.contains("Test body content."));
}

// D9: Malformed YAML
#[test]
fn d9_malformed_yaml() {
    let content = r#"---
platform: linkedin
author: [invalid yaml here
---
Some body
"#;

    let result = SocialDraft::parse(content);
    assert!(result.is_err());
    let err = result.unwrap_err().to_string();
    assert!(!err.is_empty(), "Should have parse error details");
}

// Additional: BOM handling
#[test]
fn parse_with_bom() {
    let content = "\u{feff}---\nplatform: linkedin\nauthor: btakita\n---\nBody\n";
    let draft = SocialDraft::parse(content).unwrap();
    assert_eq!(draft.meta.platform, Platform::LinkedIn);
}

// Additional: Default status is draft
#[test]
fn default_status_is_draft() {
    let content = r#"---
platform: linkedin
author: btakita
---
Body
"#;

    let draft = SocialDraft::parse(content).unwrap();
    assert_eq!(draft.meta.status, DraftStatus::Draft);
}

// Additional: Default visibility is public
#[test]
fn default_visibility_is_public() {
    let content = r#"---
platform: linkedin
author: btakita
---
Body
"#;

    let draft = SocialDraft::parse(content).unwrap();
    assert_eq!(draft.meta.visibility, "public");
}

// IM1: No images → text-only (images field absent → empty vec)
#[test]
fn im1_no_images_field() {
    let content = r#"---
platform: linkedin
author: btakita
status: ready
---
Text-only post.
"#;

    let draft = SocialDraft::parse(content).unwrap();
    assert!(draft.meta.images.is_empty());
}

// IM4: Draft round-trip with images
#[test]
fn im4_roundtrip_with_images() {
    let meta = SocialDraftMeta {
        platform: Platform::LinkedIn,
        author: "btakita".to_string(),
        visibility: "public".to_string(),
        status: DraftStatus::Ready,
        tags: vec![],
        scheduled_at: None,
        published_at: None,
        post_id: None,
        post_url: None,
        images: vec!["assets/screenshot.png".to_string(), "assets/diagram.png".to_string()],
    };

    let original = SocialDraft::new(meta, "Post with images.\n".to_string());
    let rendered = original.render().unwrap();
    let parsed = SocialDraft::parse(&rendered).unwrap();

    assert_eq!(parsed.meta.images.len(), 2);
    assert_eq!(parsed.meta.images[0], "assets/screenshot.png");
    assert_eq!(parsed.meta.images[1], "assets/diagram.png");
}

// IM6: Empty images list serialized same as no images
#[test]
fn im6_empty_images_omitted_in_yaml() {
    let meta = SocialDraftMeta {
        platform: Platform::LinkedIn,
        author: "btakita".to_string(),
        visibility: "public".to_string(),
        status: DraftStatus::Draft,
        tags: vec![],
        scheduled_at: None,
        published_at: None,
        post_id: None,
        post_url: None,
        images: vec![],
    };

    let draft = SocialDraft::new(meta, "Body.\n".to_string());
    let rendered = draft.render().unwrap();
    // Empty images should be skipped in YAML (skip_serializing_if)
    assert!(!rendered.contains("images"), "Empty images should not appear in YAML: {}", rendered);
}

// IM: Single image in frontmatter
#[test]
fn single_image_in_frontmatter() {
    let content = r#"---
platform: linkedin
author: btakita
images:
  - assets/photo.png
---
Post with one image.
"#;

    let draft = SocialDraft::parse(content).unwrap();
    assert_eq!(draft.meta.images.len(), 1);
    assert_eq!(draft.meta.images[0], "assets/photo.png");
}
