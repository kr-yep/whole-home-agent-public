using System;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;

namespace Wha.CaptureHost;

public sealed class NamedPipeProducer : IAsyncDisposable
{
    private readonly NamedPipeClientStream _pipe;
    private readonly Channel<byte[]> _queue;
    private readonly int _maxQueueCapacity;

    public NamedPipeProducer(string sessionNonce, int maxQueueCapacity = 3)
    {
        _maxQueueCapacity = maxQueueCapacity;
        // Bounded queue with 3 frame limit (Section 17)
        _queue = Channel.CreateBounded<byte[]>(new BoundedChannelOptions(maxQueueCapacity)
        {
            FullMode = BoundedChannelFullMode.DropWrite
        });

        string pipeName = $@"LOCAL\wha.capture.v1.{sessionNonce}";
        _pipe = new NamedPipeClientStream(".", pipeName, PipeDirection.Out, PipeOptions.Asynchronous);
    }

    public async Task ConnectAsync(int timeoutMs = 5000, CancellationToken ct = default)
    {
        await _pipe.ConnectAsync(timeoutMs, ct);
    }

    public async Task WriteRecordAsync(byte kind, string canonicalJsonMetadata, ReadOnlyMemory<byte> body, CancellationToken ct = default)
    {
        byte[] metaBytes = Encoding.UTF8.GetBytes(canonicalJsonMetadata);
        var prefix = new WirePrefix(kind, (uint)metaBytes.Length, (uint)body.Length);

        byte[] prefixBuffer = new byte[CaptureProtocolConstants.FixedPrefixBytes];
        prefix.WriteTo(prefixBuffer);

        await _pipe.WriteAsync(prefixBuffer, ct);
        await _pipe.WriteAsync(metaBytes, ct);
        if (!body.IsEmpty)
        {
            await _pipe.WriteAsync(body, ct);
        }
        await _pipe.FlushAsync(ct);
    }

    public async ValueTask DisposeAsync()
    {
        await _pipe.DisposeAsync();
    }
}
