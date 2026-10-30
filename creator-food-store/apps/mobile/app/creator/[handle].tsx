import { View, Text, FlatList, StyleSheet } from "react-native";
import { trpc } from "../_layout";
import { useLocalSearchParams } from "expo-router";

export default function CreatorScreen() {
  const { handle } = useLocalSearchParams<{ handle: string }>();
  const { data, isLoading } = trpc.storefront.getPublic.useQuery(
    { handle: handle ?? "" },
    { enabled: !!handle }
  );

  if (isLoading) return <Text style={styles.loading}>Loading...</Text>;
  if (!data) return <Text style={styles.loading}>Creator not found</Text>;

  const allProducts = [
    ...data.creatorProducts,
    ...data.collections.flatMap((c) => c.creatorProducts),
  ];

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{data.name}</Text>
      <Text style={styles.handle}>@{data.handle}</Text>
      {data.bio && <Text style={styles.bio}>{data.bio}</Text>}
      <Text style={styles.disclosure}>
        Affiliate disclosure: I earn commission on qualifying purchases.
      </Text>

      <FlatList
        data={allProducts}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.productName}>{item.product.name}</Text>
            {item.note && <Text style={styles.note}>&ldquo;{item.note}&rdquo;</Text>}
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fafaf9" },
  loading: { padding: 16 },
  title: { fontSize: 24, fontWeight: "bold" },
  handle: { color: "#78716c" },
  bio: { marginTop: 8, lineHeight: 20 },
  disclosure: { fontSize: 11, color: "#a8a29e", marginVertical: 12 },
  card: {
    backgroundColor: "#fff",
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#e7e5e4",
  },
  productName: { fontSize: 16, fontWeight: "600" },
  note: { fontStyle: "italic", color: "#78716c", marginTop: 4 },
});
