-- Schema para el sistema de gestión de topologías de red
-- Base de datos: PostgreSQL 16

-- Tabla de usuarios con roles
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('general', 'vip', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Tabla de plantillas (topologías guardadas, no desplegadas)
CREATE TABLE IF NOT EXISTS templates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    topology_json JSONB NOT NULL,
    availability_zone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

-- Tabla de slices (topologías desplegadas)
CREATE TABLE IF NOT EXISTS slices (
    id SERIAL PRIMARY KEY,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slice_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    topology_json JSONB NOT NULL,
    availability_zone VARCHAR(50),
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'stopped', 'error')),
    worker_info JSONB,
    vlan_info JSONB,
    vm_count INTEGER DEFAULT 0
);

-- Índices para optimizar búsquedas
CREATE INDEX IF NOT EXISTS idx_templates_user_id ON templates(user_id);
CREATE INDEX IF NOT EXISTS idx_slices_user_id ON slices(user_id);
CREATE INDEX IF NOT EXISTS idx_slices_status ON slices(status);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para templates
CREATE TRIGGER update_templates_updated_at
    BEFORE UPDATE ON templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Usuario admin por defecto (password: admin123)
-- En producción cambiar este password
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@cloudproject.com', 'pbkdf2:sha256:600000$salt$hash', 'admin')
ON CONFLICT (username) DO NOTHING;

-- Comentarios para documentación
COMMENT ON TABLE users IS 'Tabla de usuarios del sistema con roles: general, vip, admin';
COMMENT ON TABLE templates IS 'Plantillas de topologías guardadas pero no desplegadas';
COMMENT ON TABLE slices IS 'Slices desplegados activamente en la infraestructura';
COMMENT ON COLUMN users.role IS 'Roles: general (básico), vip (premium), admin (administrador)';
COMMENT ON COLUMN slices.slice_id IS 'Identificador único del slice en el orquestador';
COMMENT ON COLUMN slices.worker_info IS 'Información JSON de workers y VMs desplegadas';
COMMENT ON COLUMN slices.vlan_info IS 'Información JSON de VLANs asignadas';
