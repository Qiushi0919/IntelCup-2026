void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);
    pinMode(LED_G, OUTPUT);
    Serial.println("AMB82-MINI recovery firmware running");
}

void loop()
{
    digitalWrite(LED_B, HIGH);
    digitalWrite(LED_G, LOW);
    delay(500);

    digitalWrite(LED_B, LOW);
    digitalWrite(LED_G, HIGH);
    delay(500);
}
