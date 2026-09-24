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
-- Name: event_study; Type: INDEX; Schema: audit; Owner: -
--

CREATE INDEX event_study ON audit.event USING btree (study_uid, at);


--
-- PostgreSQL database dump complete
--

\unrestrict dbmate


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20260924000100');
