


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";





SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."signal_updates" (
    "id" integer NOT NULL,
    "signal_id" integer NOT NULL,
    "source_chat_id" bigint NOT NULL,
    "source_message_id" bigint NOT NULL,
    "source_user_id" bigint,
    "target_chat_id" bigint,
    "target_message_id" bigint,
    "original_text" "text" NOT NULL,
    "translated_text" "text",
    "image_source_url" "text",
    "image_local_path" "text",
    "image_ocr_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "processed_at" timestamp with time zone,
    "status" character varying(30) DEFAULT 'PENDING'::character varying,
    "error_message" "text",
    "forward_chat_id" bigint,
    "forward_message_id" bigint
);


ALTER TABLE "public"."signal_updates" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."signal_updates_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."signal_updates_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."signal_updates_id_seq" OWNED BY "public"."signal_updates"."id";



CREATE TABLE IF NOT EXISTS "public"."signals" (
    "id" integer NOT NULL,
    "source_chat_id" bigint NOT NULL,
    "source_message_id" bigint NOT NULL,
    "source_user_id" bigint NOT NULL,
    "target_chat_id" bigint,
    "target_message_id" bigint,
    "pair" character varying(20),
    "direction" character varying(10),
    "timeframe" character varying(20),
    "entry_range" character varying(50),
    "tp1" numeric(20,10),
    "tp2" numeric(20,10),
    "tp3" numeric(20,10),
    "sl" numeric(20,10),
    "risk_percent" double precision,
    "original_text" "text" NOT NULL,
    "translated_text" "text",
    "image_source_url" "text",
    "image_local_path" "text",
    "image_ocr_text" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "processed_at" timestamp with time zone,
    "status" character varying(30) DEFAULT 'PENDING'::character varying,
    "error_message" "text",
    "forward_chat_id" bigint,
    "forward_message_id" bigint
);


ALTER TABLE "public"."signals" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."signals_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."signals_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."signals_id_seq" OWNED BY "public"."signals"."id";



CREATE TABLE IF NOT EXISTS "public"."translation_cache" (
    "id" integer NOT NULL,
    "source_text_hash" character varying(64) NOT NULL,
    "source_text" "text" NOT NULL,
    "translated_text" "text" NOT NULL,
    "language_pair" character varying(10) DEFAULT 'ru_en'::character varying,
    "model" character varying(50),
    "created_at" timestamp with time zone DEFAULT "now"(),
    "last_used_at" timestamp with time zone DEFAULT "now"(),
    "usage_count" integer DEFAULT 1
);


ALTER TABLE "public"."translation_cache" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."translation_cache_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."translation_cache_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."translation_cache_id_seq" OWNED BY "public"."translation_cache"."id";



ALTER TABLE ONLY "public"."signal_updates" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."signal_updates_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."signals" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."signals_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."translation_cache" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."translation_cache_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."signal_updates"
    ADD CONSTRAINT "signal_updates_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."signals"
    ADD CONSTRAINT "signals_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."translation_cache"
    ADD CONSTRAINT "translation_cache_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."translation_cache"
    ADD CONSTRAINT "translation_cache_source_text_hash_key" UNIQUE ("source_text_hash");



ALTER TABLE ONLY "public"."signals"
    ADD CONSTRAINT "unique_source_msg" UNIQUE ("source_chat_id", "source_message_id");



ALTER TABLE ONLY "public"."signal_updates"
    ADD CONSTRAINT "unique_source_reply" UNIQUE ("source_chat_id", "source_message_id");



CREATE INDEX "idx_signal_updates_forward_msg" ON "public"."signal_updates" USING "btree" ("forward_message_id") WHERE ("forward_message_id" IS NOT NULL);



CREATE INDEX "idx_signals_forward_msg" ON "public"."signals" USING "btree" ("forward_message_id") WHERE ("forward_message_id" IS NOT NULL);



ALTER TABLE ONLY "public"."signal_updates"
    ADD CONSTRAINT "signal_updates_signal_id_fkey" FOREIGN KEY ("signal_id") REFERENCES "public"."signals"("id") ON DELETE CASCADE;





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";








































































































































































GRANT ALL ON TABLE "public"."signal_updates" TO "anon";
GRANT ALL ON TABLE "public"."signal_updates" TO "authenticated";
GRANT ALL ON TABLE "public"."signal_updates" TO "service_role";



GRANT ALL ON SEQUENCE "public"."signal_updates_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."signal_updates_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."signal_updates_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."signals" TO "anon";
GRANT ALL ON TABLE "public"."signals" TO "authenticated";
GRANT ALL ON TABLE "public"."signals" TO "service_role";



GRANT ALL ON SEQUENCE "public"."signals_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."signals_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."signals_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."translation_cache" TO "anon";
GRANT ALL ON TABLE "public"."translation_cache" TO "authenticated";
GRANT ALL ON TABLE "public"."translation_cache" TO "service_role";



GRANT ALL ON SEQUENCE "public"."translation_cache_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."translation_cache_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."translation_cache_id_seq" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";































drop extension if exists "pg_net";


