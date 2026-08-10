import { httpRouter } from "convex/server";
import { httpAction } from "./_generated/server";

const voiceResponse = httpAction(async () => {
  const xml = [
    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
    "<Response>",
    "<Say voice=\"Polly.Joanna-Neural\" voiceSpeed=\"0.82\">Hi Peyton! It’s Something’s Phishy.</Say>",
    "<Pause length=\"1\"/>",
    "<Say voice=\"Polly.Joanna-Neural\" voiceSpeed=\"0.82\">Logan would love a little help checking something that might be a scam.</Say>",
    "<Pause length=\"1\"/>",
    "<Say voice=\"Polly.Joanna-Neural\" voiceSpeed=\"0.82\">When you’re ready, please open the guardian dashboard, or give Logan a call. Thanks for looking out for them!</Say>",
    "</Response>",
  ].join("");

  return new Response(xml, {
    status: 200,
    headers: { "Content-Type": "application/xml" },
  });
});

const http = httpRouter();

http.route({
  path: "/voice",
  method: "POST",
  handler: voiceResponse,
});

http.route({
  path: "/voice",
  method: "GET",
  handler: voiceResponse,
});

export default http;
