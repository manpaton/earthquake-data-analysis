import argparse
import os
import sys

import analysis
import cleaner
import loader


def run_pipeline(full: bool = False) -> None:
    if full:
        import api_client
        import consumer
        import producer

        print("=== STEP 1/6: Fetching live data from USGS API ===")
        api_client.main()

        print("\n=== STEP 2/6: Streaming records to Kafka (Producer) ===")
        os.environ.setdefault("KAFKA_TOPIC", consumer.TOPIC)
        producer.main()

        print("\n=== STEP 3/6: Validating Kafka stream with Pandera (Consumer) ===")
        sys.argv = [sys.argv[0]]
        consumer.main()
    else:
        print("=== Skipping API/Kafka (using existing validated_earthquakes.json) ===")
        print("Tip: run 'python main.py --full' when Kafka is running to execute all 6 steps.")

    print("\n=== STEP 4/6: Cleaning & Feature Engineering (Pandas + NumPy) ===")
    raw_df = cleaner.load_validated_data()
    df_clean = cleaner.clean_data(raw_df)
    print(f"Loaded: {len(raw_df)} | Cleaned: {len(df_clean)}")
    cleaner.summarize_data(df_clean)

    print("\n=== STEP 5/6: Loading into SQLite (Idempotent) ===")
    total_rows = loader.save_to_sqlite(df_clean)
    print(f"Total unique records in {loader.DB_PATH.name}: {total_rows}")

    print("\n=== STEP 6/6: Statistical Analysis & Visualization ===")
    df_db = analysis.load_from_db()
    analysis.print_statistical_summary(df_db)
    analysis.run_analysis(df_db)

    print("\nPipeline completed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Earthquake Data Analysis Pipeline.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full end-to-end pipeline including USGS API and Kafka Producer/Consumer.",
    )
    args = parser.parse_args()
    run_pipeline(full=args.full)