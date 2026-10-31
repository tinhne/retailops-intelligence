"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";

import { ChartFrame } from "@/components/charts/chart-frame";
import { formatDayKey, formatTime, zoneGenericName } from "@/lib/format/datetime";
import { formatQuantity } from "@/lib/format/number";
import { useMediaQuery } from "@/lib/hooks/browser";
import { storeApi, storeKeys, type Trends } from "@/lib/api/store-api";
import { useStore } from "@/lib/store/store-context";

const DAYS = 30;

type Point = { date: string; label: string; onTime: number; late: number };

export function shipmentPoints(trends: Trends): Point[] {
  return trends.days.map((day) => ({
    date: day.date,
    label: formatDayKey(day.date),
    onTime: day.shipped_on_time,
    late: day.shipped_late,
  }));
}

/** "Shipments per day, Oct 2 to Oct 31: 695 on time, 0 late" (C-43 aria summary). */
export function shipmentSummary(points: Point[]): string {
  if (points.length === 0) return "Shipments per day: no data";
  const onTime = points.reduce((sum, point) => sum + point.onTime, 0);
  const late = points.reduce((sum, point) => sum + point.late, 0);
  return `Shipments per day, ${points[0].label} to ${points[points.length - 1].label}: ${formatQuantity(onTime)} on time, ${formatQuantity(late)} late`;
}

/** Shipments per day, on time vs late, last 30 store-local days (S-02, DESIGN_SYSTEM §16). */
export function ShipmentsChart() {
  const store = useStore();
  const wide = useMediaQuery("(min-width: 768px)");
  const query = useQuery({
    queryKey: storeKeys.trends(store.id, DAYS),
    queryFn: ({ signal }) => storeApi.trends(store.id, DAYS, signal),
  });

  const points = query.data ? shipmentPoints(query.data) : [];
  const isEmpty = points.every((point) => point.onTime + point.late === 0);
  const lastDate = points[points.length - 1]?.date;
  const partialUntil = query.data?.partial_last_day ? formatTime(query.data.as_of, store.timezone) : null;
  const height = wide ? 240 : 200;

  return (
    <ChartFrame
      title={`Shipments per day, on time vs late, last ${DAYS} days (${zoneGenericName(store.timezone)})`}
      status={query.isPending ? "loading" : query.isError ? "error" : "success"}
      error={query.error}
      onRetry={() => void query.refetch()}
      isEmpty={isEmpty}
      emptyMessage="No shipments in this period"
      ariaSummary={shipmentSummary(points)}
      height={height}
      table={{
        columns: [
          { key: "day", header: "Day" },
          { key: "onTime", header: "On time", align: "right" },
          { key: "late", header: "Late", align: "right" },
        ],
        rows: points.map((point) => ({
          day: point.date === lastDate && partialUntil ? `${point.label} (partial, until ${partialUntil})` : point.label,
          onTime: formatQuantity(point.onTime),
          late: formatQuantity(point.late),
        })),
      }}
    >
      <BarChart data={points} responsive style={{ width: "100%", height }} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={{ stroke: "var(--chart-axis)" }}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          interval={wide ? "preserveStartEnd" : 6}
          minTickGap={16}
        />
        <YAxis
          allowDecimals={false}
          tickLine={false}
          axisLine={false}
          tickCount={5}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
        />
        <Legend
          verticalAlign="top"
          align="left"
          iconType="square"
          iconSize={8}
          itemSorter={null}
          wrapperStyle={{ fontSize: 12, color: "var(--foreground)", paddingBottom: 8 }}
        />
        <Tooltip
          cursor={{ fill: "var(--surface-hover)" }}
          contentStyle={{
            background: "var(--popover)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
            boxShadow: "var(--shadow-popover)",
          }}
          labelFormatter={(label, payload) => {
            const date = (payload?.[0]?.payload as Point | undefined)?.date;
            return date === lastDate && partialUntil ? `${label} (partial day, until ${partialUntil})` : String(label);
          }}
        />
        <Bar dataKey="onTime" name="On time" stackId="shipped" fill="var(--chart-1)" maxBarSize={24} isAnimationActive={false} />
        <Bar
          dataKey="late"
          name="Late"
          stackId="shipped"
          fill="var(--chart-2)"
          maxBarSize={24}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ChartFrame>
  );
}
