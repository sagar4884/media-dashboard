# Changelog

All notable changes to this project will be documented in this file.

## [0.61] - 2025-11-18

### Added
- New Deletion Manager page to manage items marked for deletion.
- Dashboard on the Deletion Manager page to show pending deletions and reclaimable space.
- "Purge Expired" button to mass-delete items that have passed their grace period.
- "Delete Now" button for individual items on the Deletion Manager page.
- "Archived" stats on the main dashboard.
- "Archived" filter on Radarr and Sonarr pages.

### Changed
- The deletion logic is now dynamic. The grace period is calculated on the fly, and changes to the grace period setting are reflected instantly.
- Items deleted from media servers are now marked as "Archived" in the database instead of being removed.

### Fixed
- Resolved a `jinja2.exceptions.TemplateSyntaxError` on the Deletion Manager page.
- Fixed a `jinja2.exceptions.UndefinedError` by making `timedelta` available to templates.

## [0.60] - 2025-11-18

### Added
- Filtering and sorting functionality to the Radarr and Sonarr pages. Users can now filter by score and sort by title, size, and score.

### Fixed
- Resolved a `400 Bad Request` error during Tautulli sync by correctly passing the API key as a URL parameter instead of a header.

## [0.59] - 2025-11-18

### Added
- "Not Scored" button on Radarr and Sonarr pages to allow users to reset the score of an item.

### Changed
- The tag management system has been completely overhauled to use the correct Radarr/Sonarr API endpoints, ensuring real-time tag updates are reliable.
- The system will now automatically create any required `ai-` tags (`ai-keep`, `ai-delete`, etc.) if they do not already exist on the media server.

### Fixed
- Corrected a critical bug where Radarr and Sonarr tags were not updating in real-time when a score was changed in the dashboard.
- Fixed a syntax error in the Sonarr sync task that was causing it to fail.

## [0.58] - 2025-11-18

### Added
- Implemented "Full Sync" buttons for Radarr, Sonarr, and Tautulli to re-sync all data.
- Added pagination to the Radarr and Sonarr pages to improve performance with large libraries.

### Fixed
- Corrected a `jinja2.exceptions.TemplateSyntaxError` caused by incorrect `include` syntax in the Radarr and Sonarr templates.

## [0.57] - 2025-11-18

### Fixed
- Resolved an issue where Sonarr posters were incorrect and summaries were missing due to an incorrect TVDB to TMDB ID conversion.

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
