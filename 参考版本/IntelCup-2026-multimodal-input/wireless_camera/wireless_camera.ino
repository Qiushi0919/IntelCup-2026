#include "WiFi.h"
#include "StreamIO.h"
#include "VideoStream.h"
#include "RTSP.h"
#include "network_config.h"

#define CHANNEL 0

// Balanced mode: 1280 x 720, 15 FPS, H.264 RTSP at 2 Mbps.
// VIDEO_H264_JPEG keeps /snapshot.jpg available as a compatibility fallback.
VideoSetting config(1280, 720, 15, VIDEO_H264_JPEG, 1);
RTSP rtsp;
StreamIO videoStreamer(1, 1);
WiFiServer snapshotServer(80);

int status = WL_IDLE_STATUS;
uint32_t imageAddress = 0;
uint32_t imageLength = 0;
char headerBuffer[192];

void sendSnapshot(WiFiClient& client, uint8_t* image, uint32_t length)
{
    int headerLength = snprintf(
        headerBuffer,
        sizeof(headerBuffer),
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: image/jpeg\r\n"
        "Content-Length: %lu\r\n"
        "Cache-Control: no-store, no-cache, must-revalidate\r\n"
        "Pragma: no-cache\r\n"
        "Connection: close\r\n\r\n",
        length
    );
    client.write((uint8_t*)headerBuffer, headerLength);
    client.write(image, length);
}

void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);
    pinMode(LED_G, OUTPUT);

    while (status != WL_CONNECTED) {
        digitalWrite(LED_B, !digitalRead(LED_B));
        Serial.print("Connecting to Wi-Fi: ");
        Serial.println(WIFI_SSID);
        status = WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        delay(2000);
    }

    digitalWrite(LED_B, LOW);
    digitalWrite(LED_G, HIGH);

    config.setBitrate(2 * 1024 * 1024);
    config.setJpegQuality(2);
    Camera.configVideoChannel(CHANNEL, config);
    Camera.videoInit();

    rtsp.configVideo(config);
    rtsp.begin();
    videoStreamer.registerInput(Camera.getStream(CHANNEL));
    videoStreamer.registerOutput(rtsp);
    if (videoStreamer.begin() != 0) {
        Serial.println("RTSP StreamIO link failed");
    }

    Camera.channelBegin(CHANNEL);
    snapshotServer.begin();
    delay(1000);

    IPAddress ip = WiFi.localIP();
    Serial.println("Wi-Fi connected");
    Serial.print("Primary RTSP URL: rtsp://");
    Serial.print(ip);
    Serial.println(":554");
    Serial.print("Fallback snapshot URL: http://");
    Serial.print(ip);
    Serial.println("/snapshot.jpg");
    Camera.printInfo();
    rtsp.printInfo(ip.get_address());
}

void loop()
{
    // RTSP runs through StreamIO. This HTTP handler is only the fallback path.
    WiFiClient client = snapshotServer.available();
    if (!client) {
        delay(5);
        return;
    }

    bool headersComplete = false;
    bool currentLineEmpty = true;
    unsigned long requestDeadline = millis() + 3000;
    while (client.connected() && !headersComplete) {
        if (client.available()) {
            char character = client.read();
            if (character == '\n') {
                if (currentLineEmpty) {
                    headersComplete = true;
                }
                currentLineEmpty = true;
            } else if (character != '\r') {
                currentLineEmpty = false;
            }
        } else if ((long)(millis() - requestDeadline) >= 0) {
            break;
        } else {
            delay(1);
        }
    }

    if (headersComplete) {
        imageAddress = 0;
        imageLength = 0;
        Camera.getImage(CHANNEL, &imageAddress, &imageLength);
        if (imageAddress && imageLength) {
            sendSnapshot(client, (uint8_t*)imageAddress, imageLength);
        }
    }

    client.stop();
}
