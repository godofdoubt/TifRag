import pytesseract
from PIL import Image, ImageSequence, ImageEnhance, ImageFilter
import re
from datetime import datetime

def belgeyi_tara(dosya_yolu):
    try:
        img = Image.open(dosya_yolu)
        sonuclar = []
        
        for i, sayfa in enumerate(ImageSequence.Iterator(img)):
            # Görüntü işleme
            s = sayfa.convert('L')
            s = ImageEnhance.Contrast(s).enhance(2.0).filter(ImageFilter.SHARPEN)
            s = s.point(lambda p: p > 128 and 255)
            
            # OCR
            metin = pytesseract.image_to_string(s, lang='tur', config='--oem 3 --psm 6')
            satirlar = [re.sub(r'^[^a-zA-ZÇĞİÖŞÜçğıöşü]+', '', s.strip()) 
                       for s in metin.split('\n')[:15] if s.strip()]
            
            # Form ve fakülte bul
            formlar = [s for s in satirlar if 'FORMU' in s.upper()]
            fakulteler = [s for s in satirlar if 'FAKÜLTESİ' in s.upper() or 'FAKLTESİ' in s.upper()]
            
            form = min(formlar, key=len) if formlar else "Bilinmeyen Form"
            fakulte = "Bilinmeyen Fakülte"
            if fakulteler:
                f = fakulteler[0]
                kesim = f.upper().find('FAKÜLTESİ')
                if kesim == -1: kesim = f.upper().find('FAKLTESİ')
                fakulte = f[:kesim + (9 if 'Ü' in f[kesim:kesim+10] else 8)]
            
            # Tarih düzeltme ve filtreleme
            def duzelt(g, a, y):
                if len(y) == 5: y = y[1:] if y[1:].startswith(('19','20')) else y[:-1]
                if len(y) != 4 or not y.startswith(('19','20')): return None
                if len(a) >= 3: a = a[-2:]
                try:
                    ai, gi = int(a), int(g)
                    if ai > 12: ai = int(str(ai).replace('6','0',1).replace('4','0',1))
                    return f"{gi:02d}/{ai:02d}/{y}" if 1 <= ai <= 12 and 1 <= gi <= 31 else None
                except: return None
            
            tarihler = [t for t in [duzelt(g,a,y) for g,a,y in re.findall(r'(\d{1,2})\s*[./\- ]+\s*(\d{1,4})\s*[./\- ]+\s*(\d{3,5})', metin)] if t]
            
            # Benzer tarihleri grupla
            gruplar = []
            for t in tarihler:
                p = t.split('/')
                eklendi = False
                for gr in gruplar:
                    gp = gr[0].split('/')
                    if p[1:] == gp[1:] and abs(int(p[0]) - int(gp[0])) == 10:
                        gr.append(t)
                        eklendi = True
                        break
                if not eklendi: gruplar.append([t])
            
            # Her gruptan en iyi tarihi seç (31 hariç tut)
            tarihler = [min(gr, key=lambda t: (int(t.split('/')[0]) == 31) * 10) for gr in gruplar]
            
            # TC No
            tc_ler = list(set(re.findall(r'\b\d{11}\b', metin)))
            
            sonuclar.append({
                "sayfa_no": i + 1,
                "fakulte": fakulte,
                "form_turu": form,
                "tarihler": tarihler,
                "tc_nolar": tc_ler
            })
        
        return sonuclar
    except Exception as e:
        return [{"Hata": str(e)}]

# Uygulama
dosya = "Mimage.tiff"

try:
    sonuclar = belgeyi_tara(dosya)
    print(f"\n{'='*50}\nTOPLAM {len(sonuclar)} SAYFA ANALİZ SONUÇLARI\n{'='*50}")
    
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