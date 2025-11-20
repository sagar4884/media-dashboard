# Changelog

All notable changes to this project will be documented in this file.

## [0.88.0] - 2025-11-20
### Refactor
- **Architecture:** Major refactor of the backend structure. Split the monolithic `routes.py` (1000+ lines) into modular Flask Blueprints:
    - `main`: Dashboard and core routing.
    - `radarr`: Radarr list and overlay logic.
    - `sonarr`: Sonarr list and seasonal logic.
    - `tautulli`: History views.
    - `deletion`: Deletion manager.
    - `settings`: Configuration and database management.
    - `api`: Media actions and bulk operations.
- **Routes:** Deleted `app/routes.py` and updated `app/__init__.py` to register the new blueprints.
- **Templates:** Updated all Jinja2 templates to use namespaced `url_for` calls (e.g., `settings.settings` instead of `settings`).

## [0.87.2] - 2025-11-20
### Added
- **Mass Edit:** Added a "Select All" checkbox to Radarr, Sonarr, and Deletion tables for easier bulk management.
- **Shortcuts:** Implemented global keyboard shortcuts:
    - `/` to focus search.
    - `m` to toggle Mass Edit.
    - `Esc` to close modals or cancel actions.
    - `Shift + ?` to show the shortcuts help modal.
- **Persistence:** Added smart filter persistence. View mode, sort order, and per-page settings are now saved to `localStorage` and restored on page load.
- **Settings Polish:** Updated the Settings page with input icons and Toastify notifications for connection tests.

## [0.87.1] - 2025-11-20
### Added
- **UX Overhaul:** Replaced native browser alerts and confirms with Toastify.js notifications and a custom modal for a modern, non-blocking experience.
- **Search:** Added real-time search functionality to Radarr and Sonarr lists.
- **Empty States:** Added visual empty state components when no items are found in lists.
- **Feedback:** Implemented a global top-loading progress bar for HTMX requests.
- **Navigation:** Added a "Scroll to Top" button for long lists.
- **Dashboard:** Added count badges to the Command Center cards for Radarr and Sonarr.

## [0.86.9] - 2025-11-19
### Changed
- **UI Consistency:** Updated the "Keep" action icon in the Sonarr table view to use a checkmark instead of a flag/bookmark, ensuring visual consistency with the Radarr view.

## [0.86.8] - 2025-11-19
### Fixed
- **Mass Edit Visibility:** Fixed a regression where the Mass Edit floating bar was visible on page load in Radarr and Sonarr views. It now correctly stays hidden until items are selected.
- **Double Scrollbars:** Resolved an issue where data tables in Radarr, Sonarr, and Deletion Manager displayed unnecessary vertical scrollbars. Added `overflow-y-hidden` to table containers to ensure the main page scrollbar handles vertical navigation.

## [0.86.7] - 2025-11-19
### Added
- **Micro-Interactions:** Implemented a global ripple effect system for buttons to enhance tactile feedback.
    - Added `.btn-ripple` class to Sync buttons in the Dashboard and Mass Edit action buttons.
    - Implemented a vanilla JS ripple effect handler in `_layout_head.html`.
- **Entry Animations:** Added smooth entry animations to key UI components.
    - **Dashboard:** The "Command Center" card now slides in with a fade-up animation (`animate-fade-in-up`).
    - **Mass Edit Bar:** The floating Mass Edit bar now smoothly slides up from the bottom when activated.

## [0.86.6] - 2025-11-19
### Fixed
- **Hover Card Visibility:** Fixed a stacking context issue where text from subsequent table rows would bleed through or appear on top of the hover card.
    - Added `relative hover:z-50` to table rows to ensure the hovered row and its popup always sit above other content.
    - Changed the hover card background to solid `bg-gray-900` (removing opacity/blur) to prevent any content bleed-through and improve text readability.

## [0.86.5] - 2025-11-19
### Fixed
- **Mobile Menu:** Fixed an issue where the hamburger menu was unresponsive.
    - Added `x-cloak` to prevent flash of unstyled content.
    - Configured the menu to position absolutely (`absolute w-full`) to ensure it overlays content correctly instead of being hidden or displacing layout.
    - Removed inline `display: none` in favor of Alpine's reactive state management.

## [0.86.4] - 2025-11-19
### Added
- **Micro-Interactions:** Added staggered fade-in animations to all data tables (Radarr, Sonarr, Deletion) for a smoother page load experience.
- **Mobile Polish:** Integrated Alpine.js to provide smooth slide/fade transitions for the mobile navigation menu.
- **Interactive Elements:** Added `active:scale-95` press effects to mobile navigation links and the hamburger menu button for better tactile feedback.

## [0.86.3] - 2025-11-19
### Added
- **Mobile Navigation:** Implemented a responsive mobile menu with a hamburger toggle for better usability on smaller screens.
- **Responsive Tables:** Wrapped data tables in `overflow-x-auto` containers to ensure they remain accessible on mobile devices without breaking the layout.

### Fixed
- **Hover Cards:** Removed the `line-clamp-6` restriction from hover cards in Radarr, Sonarr, and Deletion tables. Summaries now expand the card vertically to fit the full text, improving readability.

## [0.86.2] - 2025-11-19
### Added
- **Enhanced Visualizations:** Upgraded the Dashboard charts to match the new glassmorphism aesthetic.
    - **Custom Styling:** Configured Chart.js to use the "Inter" font and the app's color palette with transparent backgrounds.
    - **Storage Chart:** Added a new horizontal bar chart to visualize storage usage for Movies vs TV Shows.
    - **Tooltips:** Enabled and styled chart tooltips for better data visibility.

## [0.86.1] - 2025-11-19
### Fixed
- **Hover Cards:** Fixed an issue where long titles and summaries in the hover cards were not wrapping correctly due to inherited table styles. Added `whitespace-normal` to ensure proper text display.

## [0.86.0] - 2025-11-19
### Added
- **Modern Data Tables:** Completely redesigned the list views for Radarr, Sonarr, and Deletion Manager.
    - **Sticky Headers:** Table headers now stick to the top of the view with a glassmorphism blur effect.
    - **Glass Rows:** Replaced standard table rows with floating "glass" cards for a modern look.
    - **Status Pills:** Converted text status labels into colored pills with ring borders for better visibility.
- **Tooltips:** Added native tooltips to all action buttons (Keep, Delete, Seasonal, etc.) in both Table and Poster views for better clarity.

## [0.854] - 2025-11-19
### Fixed
- **Sonarr Mass Edit:** Fixed a bug where the "Mass Edit" button in Sonarr was unresponsive due to a duplicate script inclusion.
- **Deletion Manager:** Fixed a similar duplicate script issue in the Deletion Manager.

### Changed
- **Navigation:** Updated the main header navigation to visually highlight the active page, improving wayfinding.
- **Polish:** Refined hover states and transitions in the header for a smoother feel.

## [0.853] - 2025-11-19
### Added
- **Command Center:** Transformed the dashboard's "Service Sync" panel into a modern "Command Center".
- **Visual Controls:** Added dedicated cards for Radarr, Sonarr, and Tautulli with status indicators and clear, labeled sync buttons.
- **Interactive UI:** Enhanced buttons with icons and hover effects for better feedback.

## [0.852] - 2025-11-19
### Added
- **Hero Headers:** Introduced a reusable `hero_header` macro in `_macros.html` to provide consistent, visually appealing page titles with decorative background elements.
- **Unified Design:** Implemented Hero Headers across all major pages (Dashboard, Radarr, Sonarr, Tautulli, Seasonal, Overlays, Deletion, Database, Settings).

### Changed
- **Dashboard:** Redesigned the dashboard header to integrate service health indicators directly into the Hero Header.
- **Navigation:** Updated library pages (Radarr, Sonarr) to include "Mass Edit" and view toggle controls directly within the Hero Header for better accessibility.

## [0.851] - 2025-11-19
### Added
- **Foundation:** Created `_layout_head.html` to centralize `<head>` configuration, including Tailwind CSS, Inter font, and global scripts.
- **Glassmorphism:** Implemented a modern "Glassmorphism" design language with `.glass-panel` and `.glass-header` utility classes.
- **Typography:** Switched the default font to "Inter" for a cleaner, more modern look.

### Changed
- **UI Overhaul:** Applied the new glassmorphism style to the Header, Dashboard, Radarr, Sonarr, Tautulli, Deletion, Overlays, Database, Settings, and Seasonal pages.
- **Refactor:** Replaced individual `<head>` sections in all templates with the centralized `_layout_head.html` include.

## [0.850] - 2025-11-19
### Added
- **SPA Core:** Refactored Radarr and Sonarr library views to use HTMX for Pagination, Sorting, and Filtering. This eliminates full page reloads for these actions, providing a smoother "Single Page Application" feel.
- **Partial Rendering:** Implemented server-side partial rendering for movie and show lists (`_radarr_list.html`, `_sonarr_list.html`) to support efficient HTMX updates.
- **Reusable Pagination:** Created a unified `_pagination.html` component that handles HTMX state for page navigation and "Per Page" selection.
- **URL History:** Integrated `hx-push-url` to ensure browser history and back button functionality work correctly with the new dynamic updates.

## [0.842] - 2025-11-19
### Added
- **Library Performance:** Implemented lazy loading (`loading="lazy"`) for all movie and show posters in Radarr, Sonarr, and Deletion views. This significantly improves initial page load time and reduces bandwidth usage.
- **Visual Polish:** Added CSS-based "Skeleton Loaders" (pulsing gray placeholders) for posters. This prevents layout shifts and provides a smoother visual experience while images are fetching.

## [0.841] - 2025-11-19
### Added
- **Dashboard Visuals:** Added interactive Doughnut charts using `Chart.js` to visualize "Keep vs Delete vs Unscored" statistics for Radarr and Sonarr.
- **Service Health Indicators:** Added real-time status indicators (Online/Offline/Latency) for Radarr, Sonarr, and Tautulli on the dashboard.
- **Health Check API:** Implemented a new `/health/<service>` endpoint to support the dashboard status indicators.

### Fixed
- **UI Cleanup:** Removed duplicate flash message rendering from `dashboard.html`, `settings.html`, and `deletion.html`, ensuring notifications only appear once via the new Toast system.

## [0.840] - 2025-11-19
### Added
- **Feedback Layer:** Integrated `Toastify.js` to replace standard Flask flash messages with modern, non-intrusive toast notifications.
- **Global Task Monitoring:** Implemented a persistent "Task Toast" that appears on every page when a background job is running. This allows users to navigate the app without losing track of sync progress.
- **HTMX Polling:** The global task monitor uses HTMX polling to update the progress bar and ETA in real-time.

### Changed
- **Dashboard:** Removed the local progress bar from the dashboard in favor of the global task monitor in the header.
- **UI/UX:** Improved the visual feedback for sync operations. Sync buttons now disable and show "Syncing..." state globally.

## [0.831] - 2025-11-19
### Fixed
- **Sync Bug:** Fixed a critical issue where `local_poster_path` was being assigned a tuple instead of a string during Radarr/Sonarr sync, causing a `sqlite3.ProgrammingError`.
- **Plex Integration:** Removed the `PlexOrphan` feature and its dependencies which were causing import errors.

## [0.83] - 2025-11-19
### Changed
- **Kometa Overlays:**
    - **Separate Output Files:** The overlay generation process now creates two separate files: `media_dashboard_overlays_movies.yaml` and `media_dashboard_overlays_shows.yaml`. This allows for cleaner organization and independent management of movie and show overlays in Kometa.

## [0.82] - 2025-11-19
### Added
- **Database Management:**
    - **Backup:** Added a "Backup Database" button to the Database page. Backups are saved as timestamped `.db` files in `/appdata/Backup`.
    - **Import:** Added an "Import Database" button. This allows restoring the database from the newest `.db` file found in `/appdata/Imports`.
    - **Auto-Migration:** The import process automatically applies any necessary schema updates (migrations) to ensure compatibility with the current version.
    - **Raw File Support:** The import function supports importing raw SQLite backups (including `.db-wal` and `.db-shm` files) if they are present in the Imports folder.

## [0.81] - 2025-11-19
### Changed
- **Kometa Overlays Refinement:**
    - **Split Templates:** Separated the overlay template configuration into distinct "Movies" and "TV Shows" sections for greater flexibility.
    - **ID Selection:** Added a toggle to choose between TVDB (default) and TMDB IDs for TV Shows in the generated YAML.
    - **Backend Logic:** Updated generation logic to respect the selected ID type and use separate templates.
    - **Task Update:** Enhanced background sync to fetch and store TMDB IDs for shows to support the new option.

## [0.80] - 2025-11-19
### Added
- **Kometa Overlays:** Implemented integration with Kometa (Plex Meta Manager) to display "Leaving Soon" overlays on Plex items.
    - **New Page:** Added a dedicated "Overlays" page.
    - **Template Editor:** Users can define a custom YAML template for the overlay style (position, color, text).
    - **Smart Generation:** Automatically groups expiring items by their deletion date to optimize the generated configuration file.
    - **Preview:** Real-time preview of the generated YAML based on the current deletion queue.
    - **File Output:** Generates a `media_dashboard_overlays.yaml` file in `/appdata/kometa` for Kometa to consume.
    - **Dependencies:** Added `PyYAML` to the project requirements.
    - **Database Migration:** Added automatic migration to support overlay templates.

## [0.78] - 2025-11-19
### Added
- **Seasonal Maintenance:** Implemented a new feature to automate the cleanup of "rolling" TV shows (e.g., Reality TV).
    - **New Page:** Added a dedicated "Seasonal Maintenance" page.
    - **Smart Scanning:** Scans Sonarr for shows marked as 'Seasonal'. If the newest season has a configurable number of downloaded episodes (default: 1), previous seasons are flagged for removal.
    - **Automated Cleanup:** Users can review and confirm the cleanup, which unmonitors previous seasons and deletes their files from Sonarr.
    - **Settings:** Added a global setting to define the "Minimum New Episodes" threshold.
    - **Database Migration:** Added automatic migration to support the new settings.

## [0.775] - 2025-11-19
### Fixed
- Resolved an issue where the "Leaving Soon" overlays were not displaying correctly in Plex. The integration with Kometa has been thoroughly tested and verified.

## [0.75] - 2025-11-19
### Added
- **Mass Edit Mode:** Introduced a new "Mass Edit" mode for Radarr, Sonarr, and Deletion Manager pages.
    - Users can now select multiple items using checkboxes (with Shift-Click support for ranges).
    - A floating action bar appears to perform bulk actions on selected items.
- **Bulk Actions:** Implemented backend support for mass operations including:
    - **Keep:** Mark multiple items to keep.
    - **Delete:** Mark multiple items for deletion.
    - **Seasonal:** (Sonarr only) Mark shows as seasonal.
    - **Not Scored:** Reset score for multiple items.
    - **Delete Now:** Immediately delete multiple items from the service and database.
    - **Reset Grace Period:** Reset the deletion timer for multiple items.

## [0.741] - 2025-11-19
### Fixed
- Fixed a bug in the Deletion Manager where clicking a sortable header would not reverse the sort order. The sort direction arrows were also missing.

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