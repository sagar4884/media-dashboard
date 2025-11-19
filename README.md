# Media Dashboard

A dashboard for managing your media library. This application interfaces with Radarr, Sonarr, and Tautulli to provide a centralized place to view, score, and manage your movies and TV shows.

## Features

-   **Unified Dashboard:** View summary statistics for your Radarr and Sonarr libraries in one place.
-   **Library Browsing:** Browse your movie and TV show libraries with options for table and poster views.
-   **Media Scoring:** Score your media as "Keep," "Delete," or "Seasonal" to help manage your library.
-   **Automated Tagging:** Scoring an item automatically updates its tags in Radarr or Sonarr.
-   **Tautulli Integration:** Sync your watch history from Tautulli to automatically "rescue" recently watched items that were marked for deletion.
-   **Deletion Manager:** A dedicated page to review and manage all items marked for deletion.
-   **Mass Edit Mode:** Quickly select and update multiple items at once.
-   **Seasonal Maintenance:** Automatically manage and clean up rolling TV show seasons based on episode counts.
-   **Kometa Overlays:** Generate YAML configuration files for Kometa to display "Leaving Soon" overlays on your Plex media.
-   **Database Management:** Backup, import, and maintain your application database directly from the UI.
-   **Background Syncing:** Syncs with your media servers run as background jobs, so the UI remains responsive.
-   **Dockerized:** The application is fully containerized for easy deployment.

## Deployment

This application is designed to be deployed using Docker. You can either use the provided `docker-compose.yml` file or run the container directly from Docker Hub.

### Prerequisites

-   Docker installed and running.
-   A running Redis instance. The provided `docker-compose.yml` will set one up for you, but if you are running the container directly, you will need to provide your own.

### Option 1: Using Docker Compose (Recommended)

This is the easiest way to get the application up and running.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/sagar4884/media-dashboard.git
    cd media-dashboard
    ```

2.  **Configure environment variables:**
    The `docker-compose.yml` file is pre-configured for a development environment. For a production setup, you should customize the environment variables. You can either edit the `docker-compose.yml` file directly or create a `.env` file in the same directory with the following variables:

    ```env
    # The URL for your Redis instance. If using the provided docker-compose file,
    # this should be 'redis://redis:6379/0'. Otherwise, replace with the
    # address of your Redis server.
    REDIS_URL=redis://redis:6379/0

    # The path on your host machine where all application data will be stored.
    # Replace '/path/to/your/appdata' with the actual path on your system.
    APPDATA_PATH=/path/to/your/appdata
    ```

3.  **Run the application:**
    ```bash
    docker-compose up -d
    ```

The application will now be available at `http://<your-docker-host-ip>:8000`.

### Option 2: Using Docker Run from Docker Hub

You can also run the application directly from the Docker Hub image.

```bash
docker run -d \
  --name=media-dashboard \
  -p 8000:8000 \
  -v /path/to/your/appdata:/appdata \
  -e REDIS_URL='redis://<your-redis-ip>:6379/0' \
  bladelight/media-dashboard:latest
```

**Parameters:**

-   `-p 8000:8000`: Maps the container's port 8000 to port 8000 on your host machine.
-   `-v /path/to/your/appdata:/appdata`: **(Important)** Mounts a single directory from your host machine to store all of the application's persistent data, including the database and poster images. **Replace `/path/to/your/appdata` with the actual path on your host.**
-   `-e REDIS_URL='redis://<your-redis-ip>:6379/0'`: **(Important)** Sets the URL for your Redis instance. **Replace `<your-redis-ip>` with the actual IP address of your Redis server.**

## Post-Installation Setup

Once the application is running, you will need to configure it to connect to your media servers.

1.  Open your web browser and navigate to `http://<your-docker-host-ip>:8000`.
2.  Click on the **Settings** link in the header.
3.  Enter the URL and API key for your Radarr, Sonarr, and Tautulli instances.
4.  Click **Save Settings**.
5.  Go back to the main dashboard and click the **Full Sync** buttons for Radarr, Sonarr, and Tautulli to perform the initial synchronization of your libraries. Please be patient, as the first full sync may take a long time, especially if you have a large library.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

### Data Directory Structure

The mapped `/appdata` volume will automatically populate with the following structure:

-   `/database`: Contains the SQLite database (`app.db`).
-   `/posters`: Stores downloaded media posters.
-   `/kometa`: Contains generated overlay YAML files (`media_dashboard_overlays_movies.yaml` and `media_dashboard_overlays_shows.yaml`) for use with Kometa.
-   `/Backup`: Stores database backups created via the UI.
-   `/Imports`: Place `.db` files here to import them via the UI.
