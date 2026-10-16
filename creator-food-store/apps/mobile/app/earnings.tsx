import { View, Text, StyleSheet } from "react-native";
import { trpc } from "./_layout";

export default function EarningsScreen() {
  const { data, isLoading } = trpc.analytics.dashboard.useQuery({ days: 30 });

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Earnings</Text>
      {isLoading && <Text>Loading...</Text>}
      <View style={styles.stats}>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Clicks (30d)</Text>
          <Text style={styles.statValue}>{data?.totalClicks ?? 0}</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Confirmed</Text>
          <Text style={styles.statValue}>
            ${(data?.confirmedCommission ?? 0).toFixed(2)}
          </Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Pending</Text>
          <Text style={styles.statValue}>
            ${(data?.pendingEarnings ?? 0).toFixed(2)}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fafaf9" },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 16 },
  stats: { gap: 12 },
  stat: {
    backgroundColor: "#fff",
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e7e5e4",
  },
  statLabel: { color: "#78716c", fontSize: 14 },
  statValue: { fontSize: 24, fontWeight: "bold", marginTop: 4 },
});
