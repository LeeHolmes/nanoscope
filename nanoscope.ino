void setup() {
  Serial.begin(230400);
  pinMode(A0, INPUT);  
}

void loop() {
  int measurement = analogRead(A0);

  // Transmit the integer as two bytes, big-endian
  Serial.write((measurement & 0xFF00) >> 8);
  Serial.write(measurement & 0xFF);
}
