# Store Monitoring API for Loop AI

This is a backend service to monitor restaurant store activity. It ingests store status polls, business hours, and timezone information to generate reports on store uptime and downtime. This project was developed as a take-home interview task for Loop AI.

## Tech Stack

*   **Backend:** Django, Django REST Framework
*   **Asynchronous Tasks:** Celery
*   **Message Broker/Cache:** Redis
*   **Database:** PostgreSQL
*   **Containerization:** Docker, Docker Compose

## Prerequisites

*   Docker and Docker Compose must be installed on your system.

## Getting Started

> [!IMPORTANT]
> You will need to call `/api/trigger_report/` twice. It does not work the first time around, and the reason for that is unknown.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/MatricalDefunkt/loopai-test.git
    cd loopai-test
    ```

### Build and Run

1.  Run the following command to build and start the services:
    ```bash
    docker-compose up --build
    ```
2.  The application will be available at `http://localhost:8000`.

### Loading Data

The initial data from the provided CSV files is automatically loaded into the database when the services start up, using a custom Django management command.

## API Endpoints

> [!NOTE]
> There exist endpoints for parallel processing of data, but they are unusable in their current state.

### Trigger Report

*   `POST /api/trigger_report/`
*   **Description:** Triggers the generation of a new uptime/downtime report.
*   **Request Body:** None
*   **Response:**
    *   `202 Accepted`: Returns a `report_id` for polling the report status.

    ```json
    {
      "report_id": "some-random-string"
    }
    ```

### Get Report
> Generation took 5 minutes on my machine.
*   `GET /api/get_report/{report_id}/`
*   **Description:** Retrieves the status or the result of a report generation task.
*   **URL Parameters:**
    *   `report_id` (string): The ID of the report to retrieve.
*   **Response:**
    *   If the report is still being generated:
        ```json
        {
          "status": "Running"
        }
        ```
    *   If the report is complete:
        *   Returns a `200 OK` with a downloadable CSV file.
        *   The response will have a `Content-Disposition` header set to `attachment; filename="report.csv"`.

> [!IMPORTANT]
> There is an example output in `example_output.json`. Note the 0 uptime throughout. That is because the data ends at 2024/10

## Uptime/Downtime Calculation Logic

The uptime/downtime calculation is designed to be accurate and handle various edge cases, such as stores operating 24/7, overnight business hours, and sparse data points.

### Data Preparation

1.  **Timezone Handling:** All store-related timestamps are converted to UTC to ensure consistent calculations. For stores without a specified timezone, "America/Chicago" is used as a default.
2.  **Business Hours:** Business hours are determined for each store. If a store's business hours are not defined, it is assumed to be open 24/7.
3.  **Data Freshness (8-Day Rule):** To ensure reports are based on reasonably current information, a store's status is only considered if its last recorded observation is within 8 days of the report generation time. If the last known status of a store is older than 8 days, it will not be used to extrapolate uptime/downtime for the current reporting period. In such cases, if no recent data is available for a store during its business hours, it will be considered as downtime. This 8-day window helps account for weekends and stores that might have infrequent updates but remain operational.

### Calculation Algorithm

1.  **Relevant Time Window:** The calculation is performed for three periods: the last hour, the last day, and the last week, relative to the current time (or a specified override timestamp via the `CURRENT_TIMESTAMP_OVERRIDE` Django setting).
2.  **Interpolation:** The system interpolates store status (active/inactive) between the polled data points that fall within the 8-day freshness window. When a change in store status is detected between two polls, the transition is assumed to occur at the midpoint of that interval.
3.  **Business Hours Filtering:** The calculated uptime and downtime are then intersected with the store's business hours. Only the time that falls within the business hours for each day is considered.
4.  **Extrapolation:**
    *   If the first poll for a period is after the start of business hours, the status from that poll is extrapolated backward to the beginning of the business hours.
    *   Similarly, the status from the last poll is extrapolated forward to the end of the business hours.
    *   For 24/7 stores with no data points within an interval (or only data older than 8 days), they are considered to be in a downtime state for the entire duration of that interval within the reporting period.

### Current Timestamp Override
It's possible to override the "current time" used for report generation by setting the `CURRENT_TIMESTAMP_OVERRIDE` variable in the Django settings file. If this variable is set to a valid ISO 8601 timestamp string (e.g., "2024-10-10T12:00:00Z"), that time will be used as the reference for calculating "last hour," "last day," and "last week." This is useful for testing and generating historical reports. If not set, the actual current UTC time is used.


## Future Improvements

*   **Enhanced Parallelism:** While the current implementation uses Celery for parallel processing of report generation, this can be scaled further by running multiple Celery worker instances across different machines to handle a larger volume of stores and data.
*   **Centralized Caching:** Implement a more sophisticated and centralized caching API to reduce ambiguity and ease cache access, and in turn, to reduce database load and speed up report generation.
*   **Admin Dashboard:** Develop a Django Admin dashboard to provide an interface for viewing report statuses, managing data, and manually triggering tasks.
*   **Real-time Monitoring:** Integrate with a real-time data streaming platform (like Kafka) to process store status updates as they arrive, enabling more immediate monitoring and alerting.
*   **Better Extrapolation:** We can have better extrapolation in the sense we can have "expirations" for active statuses. A store can stay "active" but not report its status for 12 hours, as an example.
