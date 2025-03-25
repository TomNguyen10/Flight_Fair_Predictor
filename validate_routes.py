import pandas as pd
import numpy as np
from fast_flights import FlightData, Passengers, Result, get_flights
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime, timedelta
import os
from typing import List, Dict, Any


def validate_route(origin: str, destination: str, dates: List[str]) -> Dict[str, Any]:
    """
    Validate if a direct flight exists between origin and destination over multiple dates
    """
    try:
        # Create flight data for each date
        flight_data = [
            FlightData(date=date, from_airport=origin, to_airport=destination)
            for date in dates
        ]

        # Get flights for all dates
        result: Result = get_flights(
            flight_data=flight_data,
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=1),
            fetch_mode="fallback"
        )

        # Check if any direct flights exist
        direct_flights = [
            {
                'date': flight_data[i].date,
                'exists': any(
                    flight.stops == 0 and flight.from_airport == origin and flight.to_airport == destination
                    for flight in result.flights
                ),
                'price': next(
                    (flight.price for flight in result.flights
                     if flight.stops == 0 and flight.from_airport == origin and flight.to_airport == destination),
                    None
                ),
                'duration': next(
                    (flight.duration for flight in result.flights
                     if flight.stops == 0 and flight.from_airport == origin and flight.to_airport == destination),
                    None
                )
            }
            for i in range(len(dates))
        ]

        return {
            'origin': origin,
            'destination': destination,
            'direct_flights': direct_flights,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'origin': origin,
            'destination': destination,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def process_routes_batch(routes_batch: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Process a batch of routes in parallel
    """
    # Generate dates for a month from now (3 consecutive days)
    start_date = datetime.now() + timedelta(days=30)
    dates = [
        (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        for i in range(3)
    ]

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_route = {
            executor.submit(validate_route, route['origin'], route['destination'], dates): route
            for route in routes_batch
        }

        for future in as_completed(future_to_route):
            result = future.result()
            results.append(result)

    return results


def main():
    # Read the international routes
    routes_df = pd.read_csv('data/international_connections.csv')

    # Convert DataFrame to list of dictionaries
    routes = routes_df.to_dict('records')

    # Process routes in batches of 50
    batch_size = 50
    all_results = []

    for i in range(0, len(routes), batch_size):
        batch = routes[i:i + batch_size]
        results = process_routes_batch(batch)
        all_results.extend(results)

        # Save intermediate results
        output_file = f'data/route_validation_{i//batch_size}.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

    # Save final results
    with open('data/route_validation_final.json', 'w') as f:
        json.dump(all_results, f, indent=2)

    # Create summary
    valid_routes = [
        r for r in all_results
        if 'direct_flights' in r and any(flight['exists'] for flight in r['direct_flights'])
    ]

    summary = {
        'total_routes': len(all_results),
        'valid_routes': len(valid_routes),
        'invalid_routes': len(all_results) - len(valid_routes),
        'validation_dates': [
            (datetime.now() + timedelta(days=30+i)).strftime('%Y-%m-%d')
            for i in range(3)
        ],
        'timestamp': datetime.now().isoformat()
    }

    with open('data/route_validation_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
