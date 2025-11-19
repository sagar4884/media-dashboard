# Changelog

All notable changes to this project will be documented in this file.

## [0.74] - 2025-11-19
### Added
- Added sorting functionality to the Deletion Manager page. Users can now sort the Radarr and Sonarr tabs by 'Title', 'Size', and 'Deletes In'.

## [0.73] - 2025-11-19
### Added
- Implemented a "Safe Stop" feature for all sync tasks. Users can now click a "Stop Sync" button to gracefully terminate a running sync. The task will save all progress it has made up to that point, allowing a "Quick Sync" to effectively resume the process later.

## [0.722] - 2025-11-19
### Fixed
- Fixed a bug where the "Test Connection" buttons on the settings page were not working. The issue was caused by the missing htmx JavaScript library.

## [0.721] - 2025-11-19
### Fixed
- Resolved a `No such file or directory` error that could occur on a clean install. The startup script now ensures the `/app/app/static` directory exists before creating the symbolic link for posters.

## [0.720] - 2025-11-19
### Changed
- Refactored the application to use a single, unified `/appdata` volume for all persistent data. This simplifies the deployment process and makes the application more robust and future-proof. All relevant files, including `docker-compose.yml`, the Unraid template, `entrypoint.sh`, and the application's core logic, have been updated to use the new data structure.

## [0.719] - 2025-11-19
### Fixed
- Corrected a flaw in the Unraid template that was causing the `REDIS_URL` to be reset to its default value on every update. The hardcoded, conflicting variable has been removed.

## [0.718] - 2025-11-19
### Changed
- The `posters` directory has been made a persistent volume in Docker. This prevents poster images from being deleted when the application is updated. The `docker-compose.yml`, Unraid template, and `README.md` have all been updated to reflect this change.

## [0.717] - 2025-11-19
### Changed
- The deletion logic for Radarr and Sonarr has been made more robust to ensure that files are deleted from the disk when an item is removed from the Deletion Manager.

## [0.716] - 2025-11-18
### Fixed
- Corrected a critical bug that was causing all poster images to be broken. The issue was caused by an incorrect order of operations in the application's initialization file.

## [0.715] - 2025-11-18
### Fixed
- Resolved a `NameError` that was causing the application to crash. The error was caused by a missing import for `StartedJobRegistry` in the global task locking mechanism.

## [0.714] - 2025-11-18
### Added
- Implemented a global locking mechanism to prevent concurrent sync and database operations. All task-related buttons are now disabled while a job is running.
- Added "Test" buttons to the settings page for Radarr, Sonarr, Tautulli, and TMDB to allow users to verify their connection settings.

### Changed
- The settings page has been restructured to move the TMDB API key into its own dedicated section.

### Fixed
- Fixed an issue where the "Settings saved" confirmation message would not appear on the settings page, instead appearing on the main dashboard.

## [0.713] - 2025-11-18
### Fixed
- Corrected a critical bug where Sonarr posters would not download because the TMDB API key was being looked up incorrectly. The system now correctly retrieves the key from the Radarr settings.
- Fixed an issue where summaries (overviews) for TV shows were not being saved during the sync process.

## [0.712] - 2025-11-18
### Fixed
- Fixed a `TypeError` on the Sonarr page caused by missing `size_gb` data. The Sonarr sync task now correctly saves the size and year for shows, and the templates have been made more robust to handle missing data.

## [0.711] - 2025-11-18
### Fixed
- Increased the timeout for Radarr and Sonarr sync jobs from 15 minutes to 3 hours to prevent `JobTimeoutException` on large libraries during a full sync.

## [0.71] - 2025-11-18
### Fixed
- Fixed an issue where the application would fail on the first run because `sqlite3` was not found. The `sqlite3` package is now installed in the Docker container.
- Fixed a `FileNotFoundError` that occurred when syncing because the `app/static/posters` directory was not being created automatically.

## [0.70] - 2025-11-18
### Changed
- The application has been consolidated into a single Docker container, simplifying deployment.
- The database migration system has been removed. The application will now create the database from the models on first run and perform an integrity check on subsequent starts.

### Fixed
- Resolved all startup errors related to database creation and migrations on fresh installations.

## [0.64] - 2025-11-18
### Fixed
- Resolved a `sqlalchemy.exc.OperationalError` that was preventing the application from starting. The error was caused by the application trying to access the database before the directory for the database file was created.

## [0.62] - 2025-11-18
### Added
- Added a database management page with integrity check, optimize, and vacuum functions.
- Added hover cards with posters and summaries to the deletion and Tautulli pages.

### Fixed
- Fixed a bug that caused the application to crash when navigating to the deletion page.
- Fixed a bug that prevented hover cards from appearing for shows on the Tautulli page.
- Fixed a bug that caused duplicate links to appear in the header.
- Fixed a bug that caused raw SQL queries to fail.

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
