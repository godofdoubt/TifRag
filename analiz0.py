import pytesseract
from PIL import Image, ImageSequence, ImageEnhance, ImageFilter
import re
import numpy as np
from PIL import ImageOps
from datetime import datetime
from difflib import SequenceMatcher

def belgeyi_tara(dosya_yolu):
    sayfa_sonuclari = []
    
    try:
        img = Image.open(dosya_yolu)
        
        for i, sayfa in enumerate(ImageSequence.Iterator(img)):
            # --- Görüntü İşleme ---
            sayfa_gray = sayfa.convert('L')
            enhancer = ImageEnhance.Contrast(sayfa_gray)
            sayfa_contrast = enhancer.enhance(2.0)
            sayfa_sharp = sayfa_contrast.filter(ImageFilter.SHARPEN)
            threshold = 128
            sayfa_bw = sayfa_sharp.point(lambda p: p > threshold and 255)
            
            # --- OCR İşlemi (TEK KAYNAK KULLAN) ---
            # Çift okuma yerine en iyi sonucu veren tek metodu kullan
            custom_config = r'--oem 3 --psm 6'
            metin = pytesseract.image_to_string(sayfa_bw, lang='tur', config=custom_config)
            
            metin_satirlar = [s.strip() for s in metin.split('\n') if s.strip()]
            
            # --- Analiz Değişkenleri ---
            sayfa_form_adi = "Bilinmeyen Form"
            sayfa_fakulte_adi = "Bilinmeyen Fakülte"
            bulunan_form_adlari = []
            
            # --- Satır Analizi ---
            for satir in metin_satirlar[:15]:  
                satir_upper = satir.upper()
                temiz_satir = re.sub(r'^[^a-zA-ZÇĞİÖŞÜçğıöşü]+', '', satir)
                
                if "FORMU" in satir_upper:
                    bulunan_form_adlari.append(temiz_satir)
                
                if "FAKÜLTESİ" in satir_upper or "FAKLTESİ" in satir_upper:
                    # "FAKÜLTESİ" kelimesinden sonrasını kes
                    if "FAKÜLTESİ" in satir_upper:
                        kesim_noktasi = temiz_satir.upper().find("FAKÜLTESİ") + len("FAKÜLTESİ")
                    else:
                        kesim_noktasi = temiz_satir.upper().find("FAKLTESİ") + len("FAKLTESİ")
                    sayfa_fakulte_adi = temiz_satir[:kesim_noktasi]
            
            if bulunan_form_adlari:
                sayfa_form_adi = min(bulunan_form_adlari, key=len)
            
            # --- Geliştirilmiş Tarih Ayıklama ---
            genis_tarih_kalibi = r'(\d{1,2})\s*[./\- ]+\s*(\d{1,4})\s*[./\- ]+\s*(\d{3,5})'
            ham_tarihler = re.findall(genis_tarih_kalibi, metin)
            
            temiz_tarihler = []
            
            def ocr_tarih_duzelt(gun, ay, yil):
                """OCR hatalarını mantıksal olarak düzeltir"""
                if len(yil) == 5: 
                    if yil[1:].startswith('19') or yil[1:].startswith('20'):
                        yil = yil[1:]
                    elif yil[:-1].startswith('19') or yil[:-1].startswith('20'):
                        yil = yil[:-1]
                
                if len(yil) != 4 or not (yil.startswith('19') or yil.startswith('20')):
                    return None

                if len(ay) >= 3:
                    ay = ay[-2:]
                
                try:
                    ay_int = int(ay)
                    gun_int = int(gun)
                except:
                    return None
                
                if ay_int > 12:
                    if str(ay_int).startswith('6'):
                        ay_int = int(str(ay_int).replace('6', '0', 1))
                    elif str(ay_int).startswith('4'):
                        ay_int = int(str(ay_int).replace('4', '0', 1))
                
                if 1 <= ay_int <= 12 and 1 <= gun_int <= 31:
                    return f"{gun_int:02d}/{ay_int:02d}/{yil}"
                
                return None

            def tarihler_benzer_mi(tarih1, tarih2, esik=0.7):
                """İki tarihin OCR hatasından mı türediğini kontrol eder"""
                benzerlik = SequenceMatcher(None, tarih1, tarih2).ratio()
                
                # Aynı yıl ve ay, sadece gün farklıysa
                parcalar1 = tarih1.split('/')
                parcalar2 = tarih2.split('/')
                
                if len(parcalar1) == 3 and len(parcalar2) == 3:
                    # Aynı ay ve yıl
                    if parcalar1[1] == parcalar2[1] and parcalar1[2] == parcalar2[2]:
                        gun1, gun2 = int(parcalar1[0]), int(parcalar2[0])
                        # Günler 1 rakam farklıysa (21 vs 31, 11 vs 21 gibi)
                        if abs(gun1 - gun2) == 10:
                            return True
                
                return benzerlik > esik

            def en_guvenilir_tarihi_sec(tarih_listesi):
                """Benzer tarihler arasından en güvenilir olanı seçer"""
                if not tarih_listesi:
                    return []
                
                # Tarihleri grupla
                gruplar = []
                for tarih in tarih_listesi:
                    eklendi = False
                    for grup in gruplar:
                        if tarihler_benzer_mi(tarih, grup[0]):
                            grup.append(tarih)
                            eklendi = True
                            break
                    if not eklendi:
                        gruplar.append([tarih])
                
                # Her gruptan en makul olanı seç
                secilmis_tarihler = []
                for grup in gruplar:
                    if len(grup) == 1:
                        secilmis_tarihler.append(grup[0])
                    else:
                        # Gruptaki tarihleri mantıksallık açısından değerlendir
                        en_iyi = min(grup, key=lambda t: tarih_skor(t))
                        secilmis_tarihler.append(en_iyi)
                
                return secilmis_tarihler

            def tarih_skor(tarih_str):
                """Tarihin ne kadar makul olduğunu skorlar (düşük = daha iyi)"""
                try:
                    gun, ay, yil = map(int, tarih_str.split('/'))
                    skor = 0
                    
                    # Bugüne olan mesafe (gelecek tarihler cezalandırılır)
                    simdi = datetime.now()
                    tarih_obj = datetime(yil, ay, gun)
                    if tarih_obj > simdi:
                        skor += 100
                    
                    # Yaygın günlere bonus (ayın 1, 15, 20, 21 gibi)
                    yaygin_gunler = [1, 15, 20, 21]
                    if gun not in yaygin_gunler:
                        skor += 5
                    
                    # 31. gün (OCR'da sıkça 21->31 hatası olur)
                    if gun == 31:
                        skor += 3
                    
                    return skor
                except:
                    return 1000

            # Ham tarihleri işle
            for g_gun, g_ay, g_yil in ham_tarihler:
                duzeltilmis = ocr_tarih_duzelt(g_gun, g_ay, g_yil)
                if duzeltilmis:
                    temiz_tarihler.append(duzeltilmis)
            
            # Benzerleri filtrele ve en güveniliri seç
            temiz_tarihler = en_guvenilir_tarihi_sec(temiz_tarihler)
            
            # --- T.C. Kimlik No ---
            tc_kalibi = r'\b\d{11}\b'
            sayfadaki_tcler = re.findall(tc_kalibi, metin)
            
            sayfa_sonuclari.append({
                "sayfa_no": i + 1,
                "fakulte": sayfa_fakulte_adi,
                "form_turu": sayfa_form_adi,
                "tarihler": temiz_tarihler,
                "tc_nolar": list(set(sayfadaki_tcler))
            })
        
        return sayfa_sonuclari
    
    except Exception as e:
        return [{"Hata": str(e)}]

# --- Uygulama ---
#dosya = "ogrenci-bilgi-formu.tiff" # Dosya adını buraya yaz
#dosya = "Akademik_Izin_Formu.tiff"
dosya = "Mimage.tiff"

try:
    sonuclar = belgeyi_tara(dosya)

    print(f"\n{'='*50}")
    print(f"TOPLAM {len(sonuclar)} SAYFA ANALİZ SONUÇLARI")
    print(f"{'='*50}")

    for s in sonuclar:
        if "Hata" in s:
            print(f"Hata: {s['Hata']}")
        else:
            print(f"\n[SAYFA {s['sayfa_no']}]")
            print(f"  Kurum/Fakülte      : {s['fakulte']}")
            print(f"  Tespit Edilen Form : {s['form_turu']}")
            print(f"  Bulunan Tarihler   : {', '.join(s['tarihler']) if s['tarihler'] else 'Bulunamadı'}")
            print(f"  T.C. Kimlik No     : {', '.join(s['tc_nolar']) if s['tc_nolar'] else 'Bulunamadı'}")
            print("-" * 50)
except Exception as main_e:
    print(f"Program çalıştırılamadı: {main_e}")