/**
 * Minimal Java client for the Project Sentinel event stream.
 *
 * Usage:
 *   javac ClientExample.java
 *   java ClientExample --host 127.0.0.1 --port 8765 --limit 5
 *
 * Pass --limit 0 (default) to keep reading until the server closes.
 */

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.Socket;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class ClientExample {
    private static final Pattern DATASET_PATTERN = Pattern.compile("\\\"dataset\\\"\\s*:\\s*\\\"(.*?)\\\"");
    private static final Pattern SEQ_PATTERN = Pattern.compile("\\\"sequence\\\"\\s*:\\s*(\\d+)");
    private static final Pattern TIMESTAMP_PATTERN = Pattern.compile("\\\"timestamp\\\"\\s*:\\s*\\\"(.*?)\\\"");
    private static final Pattern ORIGINAL_TIMESTAMP_PATTERN = Pattern.compile("\\\"original_timestamp\\\"\\s*:\\s*\\\"(.*?)\\\"");
    private static final Pattern SERVICE_PATTERN = Pattern.compile("\\\"service\\\"\\s*:\\s*\\\"(.*?)\\\"");
    private static final Pattern DATASETS_PATTERN = Pattern.compile("\\\"datasets\\\"\\s*:\\s*\\[(.*?)\\]");
    private static final Pattern EVENTS_PATTERN = Pattern.compile("\\\"events\\\"\\s*:\\s*(\\d+)");
    private static final Pattern LOOP_PATTERN = Pattern.compile("\\\"loop\\\"\\s*:\\s*(true|false)");
    private static final Pattern SPEED_PATTERN = Pattern.compile("\\\"speed_factor\\\"\\s*:\\s*([0-9.]+)");
    private static final Pattern CYCLE_PATTERN = Pattern.compile("\\\"cycle_seconds\\\"\\s*:\\s*([0-9.]+)");

    private ClientExample() {
        // utility class
    }

    public static void main(String[] args) {
        String host = "127.0.0.1";
        int port = 8765;
        int limit = 0;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--host":
                    if (i + 1 < args.length) {
                        host = args[++i];
                    }
                    break;
                case "--port":
                    if (i + 1 < args.length) {
                        port = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--limit":
                    if (i + 1 < args.length) {
                        limit = Integer.parseInt(args[++i]);
                    }
                    break;
                default:
                    System.err.println("Unknown argument: " + args[i]);
            }
        }

        try (Socket socket = new Socket(host, port);
             BufferedReader reader = new BufferedReader(
                 new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))) {

            System.out.printf("Connected to %s:%d%n", host, port);
            String line;
            int eventCount = 0;

            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) {
                    continue;
                }

                if (line.contains("\"service\"")) {
                    printBanner(line);
                    continue;
                }

                eventCount++;
                String dataset = extract(DATASET_PATTERN, line, "unknown");
                String sequence = extract(SEQ_PATTERN, line, String.valueOf(eventCount));
                String timestamp = extract(TIMESTAMP_PATTERN, line, "unknown");
                String original = extract(ORIGINAL_TIMESTAMP_PATTERN, line, "n/a");

                System.out.printf("[%d] dataset=%s sequence=%s%n", eventCount, dataset, sequence);
                System.out.printf(" timestamp: %s%n", timestamp);
                System.out.printf(" original : %s%n", original);
                System.out.println(line);
                System.out.println("-");

                if (limit > 0 && eventCount >= limit) {
                    System.out.println("Reached limit; closing connection.");
                    break;
                }
            }

            System.out.println("Stream ended.");
        } catch (UnknownHostException e) {
            System.err.println("Unknown host: " + e.getMessage());
        } catch (IOException e) {
            System.err.println("I/O error: " + e.getMessage());
        }
    }

    private static void printBanner(String line) {
        String service = extract(SERVICE_PATTERN, line, "unknown");
        String datasetsRaw = extract(DATASETS_PATTERN, line, "");
        String datasets = datasetsRaw.isEmpty() ? "unknown" : datasetsRaw.replace("\"", "").trim();
        String events = extract(EVENTS_PATTERN, line, "unknown");
        String loop = extract(LOOP_PATTERN, line, "unknown");
        String speed = extract(SPEED_PATTERN, line, "unknown");
        String cycle = extract(CYCLE_PATTERN, line, "unknown");

        System.out.println("--- Stream Banner ---");
        System.out.printf("Service: %s%n", service);
        System.out.printf("Datasets: %s%n", datasets);
        System.out.printf("Events: %s%n", events);
        System.out.printf("Looping: %s%n", loop);
        System.out.printf("Speed factor: %s%n", speed);
        System.out.printf("Cycle seconds: %s%n", cycle);
        System.out.println("---------------------");
    }

    private static String extract(Pattern pattern, String input, String fallback) {
        Matcher matcher = pattern.matcher(input);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return fallback;
    }
}
