import { VoxideClient, VoxideWidget } from "@voxide/react";

const ai = new VoxideClient({
  publicKey: import.meta.env.VITE_VOXIDE_PUBLIC_KEY || "vox_pub_...",
});

function App() {
  return <VoxideWidget client={ai} />;
}

export default App;
