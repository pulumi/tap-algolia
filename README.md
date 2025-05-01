# tap-algolia

`tap-algolia` is a Singer tap for extracting data from the Algolia Analytics API.

Built with the [Meltano Tap SDK](https://sdk.meltano.com) for Singer Taps.

## Installation

```bash
pip install tap-algolia
```

## Configuration

### Accepted Config Options

A full list of supported settings and capabilities for this
tap is available by running:

```bash
tap-algolia --about
```

### Required Configuration

| Setting           | Required | Description |
|-------------------|----------|-------------|
| application_id    | True     | Your Algolia Application ID |
| api_key           | True     | Your Algolia API Key with analytics permissions |
| indices           | True     | List of Algolia indices to extract analytics data from |

### Optional Configuration

| Setting               | Default | Description |
|-----------------------|---------|-------------|
| region                | us      | Algolia region (us or eu) |
| start_date            | 30 days ago | The earliest date to extract data from (YYYY-MM-DD) |
| end_date              | today   | The latest date to extract data to (YYYY-MM-DD) |
| include_click_analytics | True    | Whether to include click analytics metrics (CTR, position) |
| date_window_size      | 30      | Number of days to include in each API request (max 30) |

A sample configuration is included in [meltano.yml](./meltano.yml).

## Capabilities

* `catalog`
* `state`
* `discover`
* `about`
* `stream-maps`

## Streams

This tap extracts the following streams from the Algolia Analytics API:

| Stream Name           | Endpoint                        | Description                                         |
|-----------------------|---------------------------------|-----------------------------------------------------|
| top_searches          | /searches/{index}/popular       | Top search queries with click analytics metrics     |
| no_results_searches   | /searches/{index}/noresults     | Search queries that returned no results             |
| search_count          | /searches/{index}/count         | Total search count with daily breakdown             |
| no_results_rate       | /searches/{index}/noResultsRate | Percentage of searches returning no results         |
| top_results           | /searches/{index}/topResults    | Most frequently shown records in search results     |

### Data Schemas

Schema definitions are available in the [streams.py](./tap_algolia/streams.py) file.

## Usage

You can easily run `tap-algolia` by itself or in a pipeline using [Meltano](https://meltano.com/).

### Executing the Tap Directly

```bash
tap-algolia --version
tap-algolia --help
tap-algolia --config CONFIG --discover > ./catalog.json
```

## Developer Resources

### Initialize your Development Environment

```bash
pipx install poetry
poetry install
```

### Testing with [Meltano](https://www.meltano.com)

_**Note:** This tap will work in any Singer environment and does not require Meltano.
Examples here are for convenience and to streamline end-to-end orchestration scenarios._

Your project comes with a custom `meltano.yml` project file already created. Open the `meltano.yml` and follow any _"TODO"_ items listed in
the file.

Next, install Meltano (if you haven't already) and any needed plugins:

```bash
# Install meltano
pipx install meltano
# Initialize meltano within this directory
cd tap-algolia
meltano install
```

Now you can test and orchestrate using Meltano:

```bash
# Test invocation:
meltano invoke tap-algolia --version
# OR run a test `elt` pipeline:
meltano elt tap-algolia target-jsonl
```

### SDK Dev Guide

See the [dev guide](https://sdk.meltano.com/en/latest/dev_guide.html) for more instructions on how to use the SDK to 
develop your own taps and targets.