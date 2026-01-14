#include <SoftwareSerial.h>
#include <Wire.h>
#include <MPU6050.h>

SoftwareSerial BTSerial(2, 3); // RX, TX del Bluetooth
MPU6050 mpu;

#define PIEZO_PIN A0

unsigned long lastSend = 0;
const unsigned long interval = 200;
unsigned long now = 0;

// Variabili per il rilevamento del picco
int maxPiezo = 0;
int16_t maxAx = 0, maxAy = 0, maxAz = 0;

void setup() {
  BTSerial.begin(9600);    
  Wire.begin();
  mpu.initialize();
  
  // Impostiamo la sensibilità a +/- 2g per avere più dettaglio sulle buche
  // mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
}

void loop() {
  // 1. Leggi i dati grezzi istantanei
  int currentPiezo = analogRead(PIEZO_PIN);
  int16_t curAx, curAy, curAz;
  mpu.getAcceleration(&curAx, &curAy, &curAz);

  // 2. Aggiorna i massimi registrati in questo intervallo
  // Usiamo abs() perché un urto può essere sia una accelerazione positiva che negativa
  if (currentPiezo > maxPiezo) maxPiezo = currentPiezo;
  if (abs(curAx) > abs(maxAx)) maxAx = curAx;
  if (abs(curAy) > abs(maxAy)) maxAy = curAy;
  if (abs(curAz) > abs(maxAz)) maxAz = curAz;

  now = millis();
  if (now - lastSend > interval) {
    lastSend = now;

    // 3. Crea la stringa CSV con i PICCHI massimi
    // Formato: "piezo,ax,ay,az"
    String msg = String(maxPiezo) + "," + String(maxAx) + "," + String(maxAy) + "," + String(maxAz);

    // 4. Invia via Bluetooth
    BTSerial.println(msg);

    // 5. Reset dei massimi per il prossimo ciclo di 200ms
    maxPiezo = 0;
    maxAx = 0; maxAy = 0; maxAz = 0;
  }
}