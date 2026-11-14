// Independent WGC prototype. All D3D context calls occur on Qt's render thread.
#define WINDOWS_FOUNDATION_UNIVERSALAPICONTRACT_VERSION 0x130000
#include <windows.h>
#include <roapi.h>
#include <winstring.h>
#include <d3d11_1.h>
#include <dxgi1_4.h>
#include <dxgi1_2.h>
#include <d3dcompiler.h>
#include <windows.graphics.capture.h>
#include <windows.graphics.capture.interop.h>
#include <windows.foundation.h>
#include <wrl/client.h>
#include <string>
using Microsoft::WRL::ComPtr;
namespace C = ABI::Windows::Graphics::Capture;
namespace D = ABI::Windows::Graphics::DirectX::Direct3D11;
struct DxgiAccess : IUnknown {
    virtual HRESULT STDMETHODCALLTYPE GetInterface(REFIID, void**) = 0;
};
__CRT_UUID_DECL(DxgiAccess,0xa9b3d012,0x3df2,0x4ee3,0xb8,0xd1,0x86,0x95,0xf4,0x57,0xd3,0xc1)
using MakeDevice = HRESULT (WINAPI*)(IDXGIDevice*, IInspectable**);
static void check(HRESULT hr) { if (FAILED(hr)) throw hr; }
template<class T> static ComPtr<T> factory(const wchar_t *name) {
    HSTRING s{}; check(WindowsCreateString(name,(UINT32)wcslen(name),&s));
    ComPtr<T> result; HRESULT h=RoGetActivationFactory(s,__uuidof(T),(void**)result.GetAddressOf());
    WindowsDeleteString(s); check(h); return result;
}
static void closeObject(IUnknown* value) {
    if (!value) return; ComPtr<ABI::Windows::Foundation::IClosable> close;
    if (SUCCEEDED(value->QueryInterface(IID_PPV_ARGS(close.GetAddressOf())))) close->Close();
}
struct Capture {
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<D::IDirect3DDevice> rtDevice;
    ComPtr<C::IGraphicsCaptureItem> item;
    ComPtr<C::IDirect3D11CaptureFramePool> pool;
    ComPtr<C::IGraphicsCaptureSession> session;
    ComPtr<ID3D11Texture2D> texture, rgba;
    ComPtr<ID3D11ShaderResourceView> srv; ComPtr<ID3D11RenderTargetView> rtv;
    ComPtr<ID3D11VertexShader> vs;ComPtr<ID3D11PixelShader> ps;
    ComPtr<ID3D11DeviceContext1> ctx1;ComPtr<ID3DDeviceContextState> privateState;
    struct Timing {ComPtr<ID3D11Query> disjoint,start,end;bool pending=false;} timing[8];
    unsigned timingIndex=0;double gpuMs=0;bool apartment=false;
    HMONITOR monitor{}; RECT bounds{}; HWND hwnd{};
    int width=0,height=0; unsigned long long frames=0,restarts=0;
    long long timestamp=0; HRESULT error=S_OK;
    ~Capture() { stop(); rtDevice.Reset();if(apartment)RoUninitialize(); }
    void stop() { closeObject(session.Get()); session.Reset(); closeObject(pool.Get()); pool.Reset(); item.Reset(); }
    void start(HMONITOR target) {
        stop(); texture.Reset();rgba.Reset();srv.Reset();rtv.Reset(); width=height=0;
        auto supported=factory<C::IGraphicsCaptureSessionStatics>(L"Windows.Graphics.Capture.GraphicsCaptureSession");
        boolean yes=false; check(supported->IsSupported(&yes)); if(!yes) throw HRESULT(E_NOTIMPL);
        monitor=target; MONITORINFO mi{sizeof(mi)}; if(!GetMonitorInfoW(target,&mi)) throw HRESULT_FROM_WIN32(GetLastError()); bounds=mi.rcMonitor;
        auto interop=factory<IGraphicsCaptureItemInterop>(L"Windows.Graphics.Capture.GraphicsCaptureItem");
        check(interop->CreateForMonitor(target,__uuidof(C::IGraphicsCaptureItem),(void**)item.GetAddressOf()));
        ABI::Windows::Graphics::SizeInt32 size{}; check(item->get_Size(&size));
        auto statics=factory<C::IDirect3D11CaptureFramePoolStatics2>(L"Windows.Graphics.Capture.Direct3D11CaptureFramePool");
        check(statics->CreateFreeThreaded(rtDevice.Get(),ABI::Windows::Graphics::DirectX::DirectXPixelFormat_B8G8R8A8UIntNormalized,2,size,&pool));
        check(pool->CreateCaptureSession(item.Get(),&session));
        ComPtr<C::IGraphicsCaptureSession2> cursor; if(SUCCEEDED(session.As(&cursor)))cursor->put_IsCursorCaptureEnabled(false);
        // Keep the OS capture border. Never request borderless capture.
        check(session->StartCapture()); restarts++;
    }
};
extern "C" __declspec(dllexport) void* dg_create(void* qtDevice, void* window, long* result) {
    Capture* c=nullptr;
    try {
        HRESULT init=RoInitialize(RO_INIT_MULTITHREADED); if(FAILED(init)&&init!=RPC_E_CHANGED_MODE) check(init);
        c=new Capture;c->apartment=SUCCEEDED(init); c->device=(ID3D11Device*)qtDevice; c->hwnd=(HWND)window;
        if(!SetWindowDisplayAffinity(c->hwnd,0x11)) throw HRESULT_FROM_WIN32(GetLastError());
        DWORD affinity=0; if(!GetWindowDisplayAffinity(c->hwnd,&affinity)||affinity!=0x11) throw HRESULT(E_ACCESSDENIED);
        c->device->GetImmediateContext(&c->context);
        check(c->context.As(&c->ctx1));ComPtr<ID3D11Device1> dev1;check(c->device.As(&dev1));
        D3D_FEATURE_LEVEL fl=c->device->GetFeatureLevel(),used{};
        check(dev1->CreateDeviceContextState(0,&fl,1,D3D11_SDK_VERSION,__uuidof(ID3D11Device),&used,&c->privateState));
        for(auto &t:c->timing){D3D11_QUERY_DESC q{D3D11_QUERY_TIMESTAMP_DISJOINT,0};check(c->device->CreateQuery(&q,&t.disjoint));q.Query=D3D11_QUERY_TIMESTAMP;check(c->device->CreateQuery(&q,&t.start));check(c->device->CreateQuery(&q,&t.end));}
        const char* shader="Texture2D src:register(t0);struct V{float4 p:SV_Position;};V vs(uint id:SV_VertexID){V o;o.p=float4((id==2?3:-1),(id==1?3:-1),0,1);return o;}float4 ps(V v):SV_Target{return src.Load(int3(v.p.xy,0));}";
        ComPtr<ID3DBlob> vb,pb,err;
        check(D3DCompile(shader,strlen(shader),nullptr,nullptr,nullptr,"vs","vs_5_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&vb,&err));
        check(D3DCompile(shader,strlen(shader),nullptr,nullptr,nullptr,"ps","ps_5_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&pb,&err));
        check(c->device->CreateVertexShader(vb->GetBufferPointer(),vb->GetBufferSize(),nullptr,&c->vs));
        check(c->device->CreatePixelShader(pb->GetBufferPointer(),pb->GetBufferSize(),nullptr,&c->ps));
        ComPtr<IDXGIDevice> dxgi; check(c->device.As(&dxgi));
        auto make=(MakeDevice)GetProcAddress(GetModuleHandleW(L"d3d11.dll"),"CreateDirect3D11DeviceFromDXGIDevice");
        if(!make) throw HRESULT(E_NOTIMPL);
        ComPtr<IInspectable> inspect; check(make(dxgi.Get(),&inspect)); check(inspect.As(&c->rtDevice));
        c->start(MonitorFromWindow(c->hwnd,MONITOR_DEFAULTTONEAREST)); *result=S_OK; return c;
    } catch(HRESULT h) { *result=h; delete c; SetWindowDisplayAffinity((HWND)window,0); return nullptr; }
}
extern "C" __declspec(dllexport) long dg_tick(void* value, int* rect, unsigned long long* count, long long* timestamp) {
    auto c=(Capture*)value;
    try {
        check(c->device->GetDeviceRemovedReason());
        HMONITOR m=MonitorFromWindow(c->hwnd,MONITOR_DEFAULTTONEAREST);
        MONITORINFO mi{sizeof(mi)}; if(!GetMonitorInfoW(m,&mi)) throw HRESULT_FROM_WIN32(GetLastError());
        if(m!=c->monitor || !EqualRect(&mi.rcMonitor,&c->bounds)) c->start(m);
        ComPtr<C::IDirect3D11CaptureFrame> frame; check(c->pool->TryGetNextFrame(&frame));
        if(frame) {
            ABI::Windows::Graphics::SizeInt32 size{}; check(frame->get_ContentSize(&size));
            if(size.Width<=0||size.Height<=0) {closeObject(frame.Get()); return S_FALSE;}
            ComPtr<D::IDirect3DSurface> surface; check(frame->get_Surface(&surface));
            ComPtr<DxgiAccess> access; check(surface.As(&access));
            ComPtr<ID3D11Texture2D> src; check(access->GetInterface(__uuidof(ID3D11Texture2D),(void**)src.GetAddressOf()));
            D3D11_TEXTURE2D_DESC desc{}; src->GetDesc(&desc);
            if(c->width!=(int)desc.Width||c->height!=(int)desc.Height) {
                c->texture.Reset(); desc.Usage=D3D11_USAGE_DEFAULT; desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
                desc.CPUAccessFlags=0;desc.MiscFlags=0; desc.ArraySize=1;desc.MipLevels=1;
                check(c->device->CreateTexture2D(&desc,nullptr,&c->texture)); c->width=desc.Width;c->height=desc.Height;
                c->srv.Reset();c->rtv.Reset();c->rgba.Reset();
                check(c->device->CreateShaderResourceView(c->texture.Get(),nullptr,&c->srv));
                desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.BindFlags=D3D11_BIND_SHADER_RESOURCE|D3D11_BIND_RENDER_TARGET;
                check(c->device->CreateTexture2D(&desc,nullptr,&c->rgba));
                check(c->device->CreateRenderTargetView(c->rgba.Get(),nullptr,&c->rtv));
            }
            // One same-device GPU copy. No Map, staging texture, CPU pixels or keyed mutex.
            ComPtr<ID3DDeviceContextState> saved;c->ctx1->SwapDeviceContextState(c->privateState.Get(),&saved);
            auto &timing=c->timing[c->timingIndex++%8];
            if(timing.pending){D3D11_QUERY_DATA_TIMESTAMP_DISJOINT dis{};UINT64 a=0,b=0;
                if(c->context->GetData(timing.disjoint.Get(),&dis,sizeof(dis),D3D11_ASYNC_GETDATA_DONOTFLUSH)==S_OK &&
                   c->context->GetData(timing.start.Get(),&a,sizeof(a),D3D11_ASYNC_GETDATA_DONOTFLUSH)==S_OK &&
                   c->context->GetData(timing.end.Get(),&b,sizeof(b),D3D11_ASYNC_GETDATA_DONOTFLUSH)==S_OK){
                    if(!dis.Disjoint)c->gpuMs=(b-a)*1000.0/dis.Frequency;timing.pending=false;}}
            bool measuring=!timing.pending;
            if(measuring){c->context->Begin(timing.disjoint.Get());c->context->End(timing.start.Get());}
            c->context->CopyResource(c->texture.Get(),src.Get());
            // Qt's public fromNative supports RGBA only; WGC supplies BGRA.
            // Convert entirely on the GPU, never via QImage or CPU upload.
            auto ctx=c->context.Get();ID3D11RenderTargetView* target=c->rtv.Get();ID3D11ShaderResourceView* input=c->srv.Get();
            D3D11_VIEWPORT vp{0,0,(float)c->width,(float)c->height,0,1};ctx->RSSetViewports(1,&vp);
            ctx->OMSetRenderTargets(1,&target,nullptr);ctx->OMSetBlendState(nullptr,nullptr,0xffffffff);
            ctx->OMSetDepthStencilState(nullptr,0);ctx->RSSetState(nullptr);
            ctx->IASetInputLayout(nullptr);ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            ctx->VSSetShader(c->vs.Get(),nullptr,0);ctx->PSSetShader(c->ps.Get(),nullptr,0);ctx->PSSetShaderResources(0,1,&input);ctx->Draw(3,0);
            input=nullptr;ctx->PSSetShaderResources(0,1,&input);target=nullptr;ctx->OMSetRenderTargets(1,&target,nullptr);
            if(measuring){ctx->End(timing.end.Get());ctx->End(timing.disjoint.Get());timing.pending=true;}
            c->ctx1->SwapDeviceContextState(saved.Get(),nullptr);
            ABI::Windows::Foundation::TimeSpan time{}; frame->get_SystemRelativeTime(&time);c->timestamp=time.Duration;c->frames++;
            closeObject(frame.Get());
            if(size.Width!=c->width||size.Height!=c->height) {
                auto format=ABI::Windows::Graphics::DirectX::DirectXPixelFormat_B8G8R8A8UIntNormalized;
                check(c->pool->Recreate(c->rtDevice.Get(),format,2,size));
            }
        }
        RECT r{};GetClientRect(c->hwnd,&r); POINT pos{0,0};ClientToScreen(c->hwnd,&pos);
        rect[0]=pos.x-c->bounds.left;rect[1]=pos.y-c->bounds.top;rect[2]=r.right;rect[3]=r.bottom;
        rect[4]=c->width;rect[5]=c->height;*count=c->frames;*timestamp=c->timestamp; return S_OK;
    } catch(HRESULT h) { c->error=h;return h; }
}
extern "C" __declspec(dllexport) void* dg_texture(void* value) {return ((Capture*)value)->rgba.Get();}
extern "C" __declspec(dllexport) void dg_destroy(void* value) {
    if(!value)return;auto c=(Capture*)value;HWND w=c->hwnd;delete c;SetWindowDisplayAffinity(w,0);
}
// Diagnostic only: called once with an explicitly controlled synthetic desktop.
// Returns numeric center pixel, never saves pixels. Not part of the render loop.
extern "C" __declspec(dllexport) long dg_probe(void* value,unsigned char* pixel) {
 auto c=(Capture*)value;if(!c->texture)return E_PENDING;
 D3D11_TEXTURE2D_DESC desc{};c->texture->GetDesc(&desc);desc.Width=desc.Height=1;
 desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;desc.MiscFlags=0;
 ComPtr<ID3D11Texture2D> stage;HRESULT hr=c->device->CreateTexture2D(&desc,nullptr,&stage);if(FAILED(hr))return hr;
 D3D11_BOX box{500,400,0,501,401,1};c->context->CopySubresourceRegion(stage.Get(),0,0,0,0,c->texture.Get(),0,&box);
 D3D11_MAPPED_SUBRESOURCE map{};hr=c->context->Map(stage.Get(),0,D3D11_MAP_READ,0,&map);
 if(SUCCEEDED(hr)){memcpy(pixel,map.pData,4);c->context->Unmap(stage.Get(),0);}return hr;
}

extern "C" __declspec(dllexport) double dg_gpu_ms(void* value) {return ((Capture*)value)->gpuMs;}
extern "C" __declspec(dllexport) unsigned long long dg_vram(void* value) {
 auto c=(Capture*)value;ComPtr<IDXGIDevice> d;ComPtr<IDXGIAdapter> a;ComPtr<IDXGIAdapter3> a3;
 if(FAILED(c->device.As(&d))||FAILED(d->GetAdapter(&a))||FAILED(a.As(&a3)))return 0;
 DXGI_QUERY_VIDEO_MEMORY_INFO m{};if(FAILED(a3->QueryVideoMemoryInfo(0,DXGI_MEMORY_SEGMENT_GROUP_LOCAL,&m)))return 0;return m.CurrentUsage;
}
extern "C" __declspec(dllexport) void dg_pause(void* value) {if(value){auto c=(Capture*)value;c->stop();SetWindowDisplayAffinity(c->hwnd,0);}}


extern "C" __declspec(dllexport) void* dg_monitor(void* value){return ((Capture*)value)->monitor;}
