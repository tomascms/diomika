-- FKs para joins PostgREST (modelos -> categories, produtos/cores -> modelos)
ALTER TABLE modelos_aventais DROP CONSTRAINT IF EXISTS fk_modelos_aventais_categoria;
ALTER TABLE modelos_aventais ADD CONSTRAINT fk_modelos_aventais_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE avental DROP CONSTRAINT IF EXISTS fk_avental_modelo;
ALTER TABLE avental ADD CONSTRAINT fk_avental_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_aventais(id) ON DELETE CASCADE;

ALTER TABLE modelo_avental_cores DROP CONSTRAINT IF EXISTS fk_modelo_avental_cores_modelo;
ALTER TABLE modelo_avental_cores ADD CONSTRAINT fk_modelo_avental_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_aventais(id) ON DELETE CASCADE;

ALTER TABLE modelos_guarda_chuvas DROP CONSTRAINT IF EXISTS fk_modelos_guarda_chuvas_categoria;
ALTER TABLE modelos_guarda_chuvas ADD CONSTRAINT fk_modelos_guarda_chuvas_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE guarda_chuva DROP CONSTRAINT IF EXISTS fk_guarda_chuva_modelo;
ALTER TABLE guarda_chuva ADD CONSTRAINT fk_guarda_chuva_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_guarda_chuvas(id) ON DELETE CASCADE;

ALTER TABLE modelo_guarda_chuva_cores DROP CONSTRAINT IF EXISTS fk_modelo_guarda_chuva_cores_modelo;
ALTER TABLE modelo_guarda_chuva_cores ADD CONSTRAINT fk_modelo_guarda_chuva_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_guarda_chuvas(id) ON DELETE CASCADE;

ALTER TABLE modelos_luvas DROP CONSTRAINT IF EXISTS fk_modelos_luvas_categoria;
ALTER TABLE modelos_luvas ADD CONSTRAINT fk_modelos_luvas_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE luva DROP CONSTRAINT IF EXISTS fk_luva_modelo;
ALTER TABLE luva ADD CONSTRAINT fk_luva_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_luvas(id) ON DELETE CASCADE;

ALTER TABLE modelo_luva_cores DROP CONSTRAINT IF EXISTS fk_modelo_luva_cores_modelo;
ALTER TABLE modelo_luva_cores ADD CONSTRAINT fk_modelo_luva_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_luvas(id) ON DELETE CASCADE;

ALTER TABLE modelos_oculos DROP CONSTRAINT IF EXISTS fk_modelos_oculos_categoria;
ALTER TABLE modelos_oculos ADD CONSTRAINT fk_modelos_oculos_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE oculo DROP CONSTRAINT IF EXISTS fk_oculo_modelo;
ALTER TABLE oculo ADD CONSTRAINT fk_oculo_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_oculos(id) ON DELETE CASCADE;

ALTER TABLE modelo_oculo_cores DROP CONSTRAINT IF EXISTS fk_modelo_oculo_cores_modelo;
ALTER TABLE modelo_oculo_cores ADD CONSTRAINT fk_modelo_oculo_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_oculos(id) ON DELETE CASCADE;

ALTER TABLE modelos_panos_cozinha DROP CONSTRAINT IF EXISTS fk_modelos_panos_cozinha_categoria;
ALTER TABLE modelos_panos_cozinha ADD CONSTRAINT fk_modelos_panos_cozinha_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE pano_cozinha DROP CONSTRAINT IF EXISTS fk_pano_cozinha_modelo;
ALTER TABLE pano_cozinha ADD CONSTRAINT fk_pano_cozinha_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_panos_cozinha(id) ON DELETE CASCADE;

ALTER TABLE modelo_pano_cozinha_cores DROP CONSTRAINT IF EXISTS fk_modelo_pano_cozinha_cores_modelo;
ALTER TABLE modelo_pano_cozinha_cores ADD CONSTRAINT fk_modelo_pano_cozinha_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_panos_cozinha(id) ON DELETE CASCADE;

ALTER TABLE modelos_pegas DROP CONSTRAINT IF EXISTS fk_modelos_pegas_categoria;
ALTER TABLE modelos_pegas ADD CONSTRAINT fk_modelos_pegas_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE pega DROP CONSTRAINT IF EXISTS fk_pega_modelo;
ALTER TABLE pega ADD CONSTRAINT fk_pega_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_pegas(id) ON DELETE CASCADE;

ALTER TABLE modelo_pega_cores DROP CONSTRAINT IF EXISTS fk_modelo_pega_cores_modelo;
ALTER TABLE modelo_pega_cores ADD CONSTRAINT fk_modelo_pega_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_pegas(id) ON DELETE CASCADE;

ALTER TABLE modelos_regionais DROP CONSTRAINT IF EXISTS fk_modelos_regionais_categoria;
ALTER TABLE modelos_regionais ADD CONSTRAINT fk_modelos_regionais_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE regional DROP CONSTRAINT IF EXISTS fk_regional_modelo;
ALTER TABLE regional ADD CONSTRAINT fk_regional_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_regionais(id) ON DELETE CASCADE;

ALTER TABLE modelo_regional_cores DROP CONSTRAINT IF EXISTS fk_modelo_regional_cores_modelo;
ALTER TABLE modelo_regional_cores ADD CONSTRAINT fk_modelo_regional_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_regionais(id) ON DELETE CASCADE;

ALTER TABLE modelos_toalhas_mesa DROP CONSTRAINT IF EXISTS fk_modelos_toalhas_mesa_categoria;
ALTER TABLE modelos_toalhas_mesa ADD CONSTRAINT fk_modelos_toalhas_mesa_categoria FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE;

ALTER TABLE toalha_mesa DROP CONSTRAINT IF EXISTS fk_toalha_mesa_modelo;
ALTER TABLE toalha_mesa ADD CONSTRAINT fk_toalha_mesa_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_toalhas_mesa(id) ON DELETE CASCADE;

ALTER TABLE modelo_toalha_mesa_cores DROP CONSTRAINT IF EXISTS fk_modelo_toalha_mesa_cores_modelo;
ALTER TABLE modelo_toalha_mesa_cores ADD CONSTRAINT fk_modelo_toalha_mesa_cores_modelo FOREIGN KEY (id_modelo) REFERENCES modelos_toalhas_mesa(id) ON DELETE CASCADE;
