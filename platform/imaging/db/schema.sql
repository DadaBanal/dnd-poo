\restrict dbmate

-- Dumped from database version 18.6 (Debian 18.6-1.pgdg13+2)
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA audit;


--
-- Name: reading; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA reading;


--
-- Name: ris; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ris;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: event; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.event (
    id uuid DEFAULT uuidv7() NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    actor text NOT NULL,
    action text NOT NULL,
    study_uid text,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT event_action_check CHECK ((action = ANY (ARRAY['open'::text, 'claim'::text, 'release'::text]))),
    CONSTRAINT event_study_uid_check CHECK ((study_uid ~ '^[0-9.]{1,64}$'::text))
);


--
-- Name: COLUMN event.actor; Type: COMMENT; Schema: audit; Owner: -
--

COMMENT ON COLUMN audit.event.actor IS 'the Windows logon name, or a service name';


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: claim; Type: TABLE; Schema: reading; Owner: -
--

CREATE TABLE reading.claim (
    study_uid text NOT NULL,
    reader text NOT NULL,
    reader_name text NOT NULL,
    claimed_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT claim_study_uid_check CHECK ((study_uid ~ '^[0-9.]{1,64}$'::text))
);


--
-- Name: COLUMN claim.reader; Type: COMMENT; Schema: reading; Owner: -
--

COMMENT ON COLUMN reading.claim.reader IS 'the reader''s Windows logon name (AD sAMAccountName)';


--
-- Name: event; Type: TABLE; Schema: ris; Owner: -
--

CREATE TABLE ris.event (
    id uuid DEFAULT uuidv7() NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    actor text NOT NULL,
    action text NOT NULL,
    order_no text NOT NULL,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: order_map; Type: TABLE; Schema: ris; Owner: -
--

CREATE TABLE ris.order_map (
    order_no text NOT NULL,
    accession text NOT NULL,
    patient_id text NOT NULL,
    study_uid text NOT NULL,
    worklist_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    tags_hash text NOT NULL,
    change_seq bigint NOT NULL,
    state text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT order_map_accession_check CHECK (((length(accession) >= 1) AND (length(accession) <= 16))),
    CONSTRAINT order_map_state_check CHECK ((state = ANY (ARRAY['SCHEDULED'::text, 'PERFORMED'::text, 'CANCELLED'::text, 'NEEDS_REVIEW'::text]))),
    CONSTRAINT order_map_study_uid_check CHECK ((study_uid ~ '^[0-9.]{1,64}$'::text))
);


--
-- Name: sync_cursor; Type: TABLE; Schema: ris; Owner: -
--

CREATE TABLE ris.sync_cursor (
    name text NOT NULL,
    value bigint NOT NULL
);


--
-- Name: event event_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.event
    ADD CONSTRAINT event_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: claim claim_pkey; Type: CONSTRAINT; Schema: reading; Owner: -
--

ALTER TABLE ONLY reading.claim
    ADD CONSTRAINT claim_pkey PRIMARY KEY (study_uid);


--
-- Name: event event_pkey; Type: CONSTRAINT; Schema: ris; Owner: -
--

ALTER TABLE ONLY ris.event
    ADD CONSTRAINT event_pkey PRIMARY KEY (id);


--
-- Name: order_map order_map_accession_key; Type: CONSTRAINT; Schema: ris; Owner: -
--

ALTER TABLE ONLY ris.order_map
    ADD CONSTRAINT order_map_accession_key UNIQUE (accession);


--
-- Name: order_map order_map_pkey; Type: CONSTRAINT; Schema: ris; Owner: -
--

ALTER TABLE ONLY ris.order_map
    ADD CONSTRAINT order_map_pkey PRIMARY KEY (order_no);


--
-- Name: sync_cursor sync_cursor_pkey; Type: CONSTRAINT; Schema: ris; Owner: -
--

ALTER TABLE ONLY ris.sync_cursor
    ADD CONSTRAINT sync_cursor_pkey PRIMARY KEY (name);


--
-- Name: event_study; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX event_study ON audit.event USING btree (study_uid, at);


--
-- Name: event_order; Type: INDEX; Schema: ris; Owner: -
--

CREATE INDEX event_order ON ris.event USING btree (order_no, at);


--
-- Name: order_map_study; Type: INDEX; Schema: ris; Owner: -
--

CREATE INDEX order_map_study ON ris.order_map USING btree (study_uid);


--
-- PostgreSQL database dump complete
--

\unrestrict dbmate


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20260924000100'),
    ('20260924000200');
