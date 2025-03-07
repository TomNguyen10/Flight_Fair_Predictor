import csv
import os
import time
import argparse
from collections import defaultdict
from typing import Dict, List, Set
from datetime import datetime, timedelta

# Import fast-flights functions
from fast_flights import FlightData, Passengers, get_flights


def read_airports_csv(csv_path: str) -> List[str]:
    """Read airport codes from the CSV file."""
    airport_codes = []
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Use the 'code' column from airports.csv
            airport_codes.append(row['code'])
    return airport_codes


def check_direct_flights(airports: List[str], sample_size: int = None, delay: float = 1.0) -> Dict[str, List[str]]:
    """
    Check for direct flights between airports over a week-long period.

    Args:
        airports: List of airport codes
        sample_size: Optional limit for testing (to avoid long processing times)
        delay: Time to wait between API calls to avoid rate limiting

    Returns:
        A dictionary where keys are source airports and values are lists of destination airports
    """
    # Use a defaultdict to automatically create empty lists for new keys
    direct_flights_map = defaultdict(list)

    # For testing purposes, limit the number of airports if sample_size is provided
    if sample_size:
        airports = airports[:sample_size]

    total_airports = len(airports)

    # Generate a range of dates for a week in the future
    start_date = datetime.now() + timedelta(days=30)  # Start 30 days from now
    check_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                   for i in range(7)]
    print(f"Checking flights for dates: {', '.join(check_dates)}")

    for i, source_airport in enumerate(airports):
        print(f"Processing {source_airport} ({i+1}/{total_airports})...")

        # Skip airports with invalid codes (too short, etc.)
        if len(source_airport) < 3:
            continue

        for destination_airport in airports:
            # Skip self-connections and invalid codes
            if source_airport == destination_airport or len(destination_airport) < 3:
                continue

            has_direct_flight = False

            # Check each date in the week range
            for check_date in check_dates:
                try:
                    # Check for direct flights on this date
                    result = get_flights(
                        flight_data=[
                            FlightData(
                                date=check_date,
                                from_airport=source_airport,
                                to_airport=destination_airport
                            )
                        ],
                        trip="one-way",
                        seat="economy",
                        passengers=Passengers(
                            adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
                        fetch_mode="fallback",  # Use fallback mode for more reliable results
                        max_stops=0  # Ensure direct flights only
                    )

                    # If flights are found on any day, add to the map and break the loop
                    if result and result.flights:
                        direct_flights_map[source_airport].append(
                            destination_airport)
                        print(
                            f"  Direct flight found: {source_airport} -> {destination_airport} on {check_date}")
                        has_direct_flight = True
                        break  # No need to check other dates

                    # Short delay to avoid rate limiting
                    time.sleep(delay)

                except Exception as e:
                    print(
                        f"  Error checking {source_airport} -> {destination_airport} on {check_date}: {str(e)}")
                    time.sleep(delay * 2)  # Wait longer after errors

            if not has_direct_flight:
                print(
                    f"  No direct flights found: {source_airport} -> {destination_airport}")

    return direct_flights_map


def save_to_csv(direct_flights_map: Dict[str, List[str]], output_path: str) -> None:
    """Save the direct flights map to a CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['source_airport', 'destination_airports'])

        for source, destinations in direct_flights_map.items():
            # Join the list of destinations with commas
            writer.writerow([source, ','.join(destinations)])


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate a map of direct flights between airports.')
    parser.add_argument('--sample-size', type=int,
                        help='Limit the number of airports to process (for testing)')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Delay in seconds between API calls (default: 1.0)')
    return parser.parse_args()


def main():
    # Parse command-line arguments
    args = parse_args()

    # Paths
    data_dir = 'data'
    airports_csv = os.path.join(data_dir, 'airports.csv')
    output_csv = os.path.join(data_dir, 'direct_flights_map.csv')

    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)

    # Read airport codes
    airports = read_airports_csv(airports_csv)

    # Check for direct flights
    direct_flights_map = check_direct_flights(
        airports,
        sample_size=args.sample_size,
        delay=args.delay
    )

    # Save the results
    save_to_csv(direct_flights_map, output_csv)
    print(f"Direct flights map saved to {output_csv}")


if __name__ == "__main__":
    main()
