import { View, Text, FlatList, StyleSheet } from "react-native";
import { trpc } from "./_layout";

export default function LockerScreen() {
  const { data, isLoading } = trpc.consumer.locker.useQuery();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>My Locker</Text>
      {isLoading && <Text>Loading...</Text>}
      <FlatList
        data={data ?? []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{item.product.name}</Text>
            {item.product.priceCents && (
              <Text style={styles.price}>
                ${(item.product.priceCents / 100).toFixed(2)}
              </Text>
            )}
            {item.isPurchased && <Text style={styles.badge}>Purchased</Text>}
          </View>
        )}
        ListEmptyComponent={
          <Text style={styles.empty}>No saved products yet.</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fafaf9" },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 16 },
  card: {
    backgroundColor: "#fff",
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#e7e5e4",
  },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  price: { color: "#059669", marginTop: 4 },
  badge: { color: "#059669", fontSize: 12, marginTop: 4 },
  empty: { color: "#78716c", textAlign: "center", marginTop: 32 },
});
