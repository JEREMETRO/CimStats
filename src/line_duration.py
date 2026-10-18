"""Integer timing shared by full-line and direction runtime calculations."""


def vehicle_duration_ticks(distance, average_speed, stop_time, stop_count, frame_time_span):
    """Mirror VehicleTypeObject.CalculateDuration before any full-line rounding."""
    return ((distance * 16) // average_speed + stop_count * stop_time * 60) * frame_time_span
