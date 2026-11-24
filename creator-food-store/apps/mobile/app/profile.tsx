import { View, Text, StyleSheet } from "react-native";

export default function ProfileScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Profile</Text>
      <Text style={styles.sub}>
        Sign in via the web app to manage your creator storefront and profile
        settings.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fafaf9" },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 8 },
  sub: { color: "#78716c", lineHeight: 22 },
});
