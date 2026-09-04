using System;
using System.Diagnostics;
using System.Threading.Tasks;

namespace Wha.CaptureHost;

public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        string? nonce = null;
        bool synthetic = false;
        int frameCount = 300;

        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--session-nonce" && i + 1 < args.Length)
            {
                nonce = args[++i];
            }
            else if (args[i] == "--synthetic")
            {
                synthetic = true;
            }
            else if (args[i] == "--frames" && i + 1 < args.Length && int.TryParse(args[++i], out int fc))
            {
                frameCount = fc;
            }
        }

        if (string.IsNullOrEmpty(nonce) || nonce.Length != 32)
        {
            Console.Error.WriteLine("Error: Valid 32-character --session-nonce is required.");
            return 1;
        }

        Console.WriteLine($"[CaptureHost] Starting session {nonce}, synthetic={synthetic}");

        await using var producer = new NamedPipeProducer(nonce);
        try
        {
            await producer.ConnectAsync(5000);
            Console.WriteLine("[CaptureHost] Connected to SemanticHost named pipe.");
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[CaptureHost] Pipe connection failed: {ex.Message}");
            return 2;
        }

        long qpcFreq = Stopwatch.Frequency;
        long startQpc = Stopwatch.GetTimestamp();
        ulong startMonotonicNs = (ulong)(startQpc * 1_000_000_000L / qpcFreq);

        string configHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
        using var digest = new StreamDigestCalculator(configHash, 1280, 720, 10, 1, startMonotonicNs);

        // 1. Emit START
        string startMeta = $"{{\"activation_decision_id\":null,\"audio_enabled\":false,\"capture_config_hash\":\"{configHash}\",\"capture_session_id\":\"{nonce}\",\"height\":720,\"kind\":\"start\",\"network_egress_enabled\":false,\"pixel_format\":\"rgb24\",\"policy_version\":null,\"raw_retention\":\"none\",\"schema\":\"whole-home-agent.capture-message.v1\",\"source_id\":\"windows-capture-01\",\"source_profile\":\"windows_generated_ipc_v1\",\"started_monotonic_ns\":{startMonotonicNs},\"target_fps_denominator\":1,\"target_fps_numerator\":10,\"width\":1280}}";
        await producer.WriteRecordAsync(CaptureProtocolConstants.KindStart, startMeta, ReadOnlyMemory<byte>.Empty);

        // 2. Emit FRAMES
        byte[] frameBody = new byte[CaptureProtocolConstants.FrameBodyBytes];
        for (int seq = 0; seq < frameCount; seq++)
        {
            long nowQpc = Stopwatch.GetTimestamp();
            ulong nowNs = (ulong)(nowQpc * 1_000_000_000L / qpcFreq);

            // Fill synthetic pattern
            byte fillVal = (byte)(seq % 256);
            Array.Fill(frameBody, fillVal);

            digest.UpdateFrame((ulong)seq, nowNs, frameBody);

            string frameMeta = $"{{\"capture_session_id\":\"{nonce}\",\"captured_monotonic_ns\":{nowNs},\"height\":720,\"kind\":\"frame\",\"pixel_format\":\"rgb24\",\"schema\":\"whole-home-agent.capture-message.v1\",\"source_id\":\"windows-capture-01\",\"source_sequence\":{seq},\"width\":1280}}";
            await producer.WriteRecordAsync(CaptureProtocolConstants.KindFrame, frameMeta, frameBody);

            // 10 Hz pacing (100 ms)
            await Task.Delay(100);
        }

        // 3. Emit SEALED END
        string streamSha = digest.FinalizeHex();
        long endQpc = Stopwatch.GetTimestamp();
        ulong endNs = (ulong)(endQpc * 1_000_000_000L / qpcFreq);
        int lastSeq = frameCount - 1;

        string endMeta = $"{{\"capture_session_id\":\"{nonce}\",\"dropped_frame_count\":0,\"ended_monotonic_ns\":{endNs},\"failure_code\":null,\"frame_count\":{frameCount},\"kind\":\"end\",\"last_source_sequence\":{lastSeq},\"schema\":\"whole-home-agent.capture-message.v1\",\"source_id\":\"windows-capture-01\",\"status\":\"SEALED\",\"stream_sha256\":\"{streamSha}\"}}";
        await producer.WriteRecordAsync(CaptureProtocolConstants.KindEnd, endMeta, ReadOnlyMemory<byte>.Empty);

        Console.WriteLine("[CaptureHost] Session completed and sealed.");
        return 0;
    }
}
