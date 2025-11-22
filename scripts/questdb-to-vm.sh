#!/bin/bash
# Export QuestDB data and import to VictoriaMetrics

QUESTDB_URL="http://127.0.0.1:9000"
VM_URL="http://127.0.0.1:8428"
TMPDIR="/tmp/quest-export"

mkdir -p "$TMPDIR"

echo "=== Exporting QuestDB data to VictoriaMetrics ==="

# Export furnace table
echo "Exporting furnace table..."
curl -s -G "$QUESTDB_URL/exp" \
  --data-urlencode "query=SELECT * FROM furnace ORDER BY timestamp" \
  -o "$TMPDIR/furnace.csv"
FURNACE_ROWS=$(wc -l < "$TMPDIR/furnace.csv")
echo "  Exported $((FURNACE_ROWS - 1)) rows"

# Export pressure table
echo "Exporting pressure table..."
curl -s -G "$QUESTDB_URL/exp" \
  --data-urlencode "query=SELECT * FROM pressure ORDER BY timestamp" \
  -o "$TMPDIR/pressure.csv"
PRESSURE_ROWS=$(wc -l < "$TMPDIR/pressure.csv")
echo "  Exported $((PRESSURE_ROWS - 1)) rows"

# Export environment table
echo "Exporting environment table..."
curl -s -G "$QUESTDB_URL/exp" \
  --data-urlencode "query=SELECT * FROM environment ORDER BY timestamp" \
  -o "$TMPDIR/environment.csv"
ENV_ROWS=$(wc -l < "$TMPDIR/environment.csv")
echo "  Exported $((ENV_ROWS - 1)) rows"

# Convert and import furnace data
# Columns: host, furnace_temp, cold_junction, flame_voltage, inlet_pressure, outlet_pressure, timestamp
echo ""
echo "Converting and importing furnace data..."
tail -n +2 "$TMPDIR/furnace.csv" | awk -F',' '
{
  gsub(/"/, "", $1); host=$1
  furnace_temp=$2
  cold_junction=$3
  flame_voltage=$4
  inlet_pressure=$5
  outlet_pressure=$6
  gsub(/"/, "", $7); ts=$7

  fields=""
  if (furnace_temp != "") fields=fields "furnace_temp=" furnace_temp ","
  if (cold_junction != "") fields=fields "cold_junction=" cold_junction ","
  if (flame_voltage != "") fields=fields "flame_voltage=" flame_voltage ","
  if (inlet_pressure != "") fields=fields "inlet_pressure=" inlet_pressure ","
  if (outlet_pressure != "") fields=fields "outlet_pressure=" outlet_pressure ","

  if (fields != "") {
    sub(/,$/, "", fields)
    print "furnace,host=" host " " fields " " ts
  }
}' > "$TMPDIR/furnace.lp"

FURNACE_LP=$(wc -l < "$TMPDIR/furnace.lp")
echo "  Converted $FURNACE_LP lines to line protocol"

# Import to VictoriaMetrics in batches
echo "  Importing to VictoriaMetrics..."
split -l 10000 "$TMPDIR/furnace.lp" "$TMPDIR/furnace_batch_"
for batch in "$TMPDIR"/furnace_batch_*; do
  curl -s -X POST "$VM_URL/write" --data-binary @"$batch"
  echo -n "."
done
echo " done"

# Convert and import pressure data
# Columns: host, pressure_inlet, pressure_outlet, timestamp, inlet_v, ref_v, inlet_raw
echo ""
echo "Converting and importing pressure data..."
tail -n +2 "$TMPDIR/pressure.csv" | awk -F',' '
{
  gsub(/"/, "", $1); host=$1
  pressure_inlet=$2
  pressure_outlet=$3
  gsub(/"/, "", $4); ts=$4
  inlet_v=$5
  ref_v=$6
  inlet_raw=$7

  fields=""
  if (pressure_inlet != "") fields=fields "pressure_inlet=" pressure_inlet ","
  if (pressure_outlet != "") fields=fields "pressure_outlet=" pressure_outlet ","
  if (inlet_v != "") fields=fields "inlet_v=" inlet_v ","
  if (ref_v != "") fields=fields "ref_v=" ref_v ","
  if (inlet_raw != "") fields=fields "inlet_raw=" inlet_raw "i,"

  if (fields != "") {
    sub(/,$/, "", fields)
    print "pressure,host=" host " " fields " " ts
  }
}' > "$TMPDIR/pressure.lp"

PRESSURE_LP=$(wc -l < "$TMPDIR/pressure.lp")
echo "  Converted $PRESSURE_LP lines to line protocol"

echo "  Importing to VictoriaMetrics..."
split -l 10000 "$TMPDIR/pressure.lp" "$TMPDIR/pressure_batch_"
for batch in "$TMPDIR"/pressure_batch_*; do
  curl -s -X POST "$VM_URL/write" --data-binary @"$batch"
  echo -n "."
done
echo " done"

# Convert and import environment data
# Columns: host, temperature, pressure, humidity, timestamp
echo ""
echo "Converting and importing environment data..."
tail -n +2 "$TMPDIR/environment.csv" | awk -F',' '
{
  gsub(/"/, "", $1); host=$1
  temperature=$2
  pressure=$3
  humidity=$4
  gsub(/"/, "", $5); ts=$5

  fields=""
  if (temperature != "") fields=fields "temperature=" temperature ","
  if (pressure != "") fields=fields "pressure=" pressure ","
  if (humidity != "") fields=fields "humidity=" humidity ","

  if (fields != "") {
    sub(/,$/, "", fields)
    print "environment,host=" host " " fields " " ts
  }
}' > "$TMPDIR/environment.lp"

ENV_LP=$(wc -l < "$TMPDIR/environment.lp")
echo "  Converted $ENV_LP lines to line protocol"

echo "  Importing to VictoriaMetrics..."
curl -s -X POST "$VM_URL/write" --data-binary @"$TMPDIR/environment.lp"
echo " done"

echo ""
echo "=== Migration complete ==="
echo "Temporary files in $TMPDIR"
