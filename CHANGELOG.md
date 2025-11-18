# Changelog

All notable changes to this project will be documented in this file.

## [0.56] - 2025-11-18

### Fixed
- Corrected an issue where the hover card summary was not displaying due to a missing `overview` attribute in the database.
- Fixed the positioning of the hover card, which was previously appearing in the wrong location.
- Resolved an issue where long summaries would overflow the hover card by increasing the card's width.

### Changed
- Increased the poster size on the hover card by 50% for better visibility.

## [0.55] - 2025-11-18

### Fixed
- Resolved a `NoSuchJobError` when polling for completed jobs. The application now gracefully handles cases where a job has been cleared from the queue.
- Addressed a Gunicorn `WORKER TIMEOUT` error by increasing the worker timeout to 120 seconds, making the web server more resilient to slow database queries.

## [0.5] - 2025-11-18

### Added
- The main dashboard now displays a summary of Radarr and Sonarr library statistics.
- New "Seasonal" action for Sonarr to manage shows with the `ai-rolling-keep` tag.
- Sync logic now automatically scores items based on `ai-keep`, `ai-delete`, and `ai-rolling-keep` tags.

### Changed
- Action buttons for Keep/Delete/Seasonal now add and remove tags in Radarr/Sonarr instead of directly modifying the local database score.

### Fixed
- Resolved a `TypeError` in Radarr/Sonarr sync tasks caused by incorrect handling of tag data. The sync logic now correctly maps tag IDs to labels.
- Fixed a `JobTimeoutException` during initial library syncs by increasing the job timeout to 15 minutes.

## [0.4] - 2025-11-18

### Added
- View toggle on Radarr and Sonarr pages to switch between table and poster views.
- Poster grid view for Radarr and Sonarr libraries.
- Hover-to-show-summary functionality on poster view.
- Hover card with larger poster and summary in table view.

### Fixed
- Corrected a CSS overflow issue where long summaries would break the layout of the table view hover card. The card now wraps text and expands vertically to fit the content.
