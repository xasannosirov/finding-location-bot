CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_tg_id BIGINT NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(15) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    start_location TEXT NOT NULL,
    current_location TEXT,
    end_location TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);
