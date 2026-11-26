-- BIST Asistan · Supabase kurulumu (bir kez, Supabase panelinde SQL Editor'e yapıştırıp çalıştırın)
--
-- Güvenlik modeli (satır düzeyi güvenlik, RLS):
--   * Uygulamanın anahtarı (publishable / anon): aktif duyuruları OKUR, geri bildirim EKLER
--     (okuyamaz), veri dosyalarını OKUR. Hiçbir şeyi silemez ya da değiştiremez.
--   * Admin anahtarı (secret / service_role): RLS'i aşar; sadece yerel .env'de durur.

-- ---------------------------------------------------------------------------
-- Tablolar
-- ---------------------------------------------------------------------------
create table if not exists public.duyurular (
  id         bigint generated always as identity primary key,
  baslik     text        not null check (char_length(baslik) between 1 and 80),
  metin      text        not null check (char_length(metin) between 1 and 500),
  tur        text        not null default 'bilgi' check (tur in ('bilgi', 'uyari', 'onemli')),
  olusturma  timestamptz not null default now(),
  bitis      date,
  aktif      boolean     not null default true
);

create table if not exists public.geri_bildirimler (
  id     bigint generated always as identity primary key,
  zaman  timestamptz not null default now(),
  sekme  text        not null check (char_length(sekme) between 1 and 40),
  puan   smallint    not null check (puan in (-1, 1)),
  notu   text        check (notu is null or char_length(notu) <= 200)
);

alter table public.duyurular enable row level security;
alter table public.geri_bildirimler enable row level security;

drop policy if exists "herkes aktif duyurulari okur" on public.duyurular;
create policy "herkes aktif duyurulari okur" on public.duyurular
  for select to anon
  using (aktif and (bitis is null or bitis >= current_date));

drop policy if exists "herkes geri bildirim ekler" on public.geri_bildirimler;
create policy "herkes geri bildirim ekler" on public.geri_bildirimler
  for insert to anon
  with check (true);   -- uzunluk ve puan sınırları tablo kısıtlarıyla zorunlu

-- ---------------------------------------------------------------------------
-- Veri dosyaları (özel depolama alanı; herkese açık link yok)
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('veri', 'veri', false)
on conflict (id) do nothing;

drop policy if exists "uygulama veri dosyalarini okur" on storage.objects;
create policy "uygulama veri dosyalarini okur" on storage.objects
  for select to anon
  using (bucket_id = 'veri');

-- ---------------------------------------------------------------------------
-- Tablo izinleri (yeni projelerde tablolar hiçbir role otomatik açılmaz)
-- ---------------------------------------------------------------------------
grant usage on schema public to anon, service_role;
grant select, insert, update, delete on public.duyurular, public.geri_bildirimler to service_role;
grant select on public.duyurular to anon;
grant insert on public.geri_bildirimler to anon;
