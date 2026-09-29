import { PageHeader } from "@/components/ui";
import { VoiceDemo } from "@/components/voice-demo";

export default function Home() {
  return (
    <>
      <PageHeader
        title="Talk to Maya"
        description="Lauki Phones' AI customer care agent. Call from the browser, or dial the Twilio number."
      />
      <VoiceDemo />
    </>
  );
}
