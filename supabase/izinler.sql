-- BIST Asistan · tablo izinleri (kurulum.sql'den SONRA, bir kez çalıştırın)
--
-- Yeni Supabase projelerinde SQL ile oluşturulan tablolar hiçbir role otomatik açılmaz.
-- En az yetki ilkesi: her rol sadece ihtiyacı olan işlemi yapabilir; satır düzeyindeki
-- kısıtlar ayrıca kurulum.sql'deki RLS politikalarıyla uygulanır.

grant usage on schema public to anon, service_role;

-- Admin (secret anahtar, sadece yerel bilgisayarda): tam yetki
grant select, insert, update, delete on public.duyurular, public.geri_bildirimler to service_role;

-- Uygulama (publishable anahtar): duyuruları sadece okur, geri bildirimi sadece ekler
grant select on public.duyurular to anon;
grant insert on public.geri_bildirimler to anon;
