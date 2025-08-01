// Package pinsbind contains all the code related to the PINS project's binding to Ondatra.
package pinsbind

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

       "flag"

	log "github.com/golang/glog"

	"github.com/openconfig/gnoigo"
        pinsbackend "github.com/sonic-net/sonic-mgmt/sdn_tests/pins_ondatra/infrastructure/binding/pinsbackend"
        "google.golang.org/grpc"

	"github.com/openconfig/ondatra/binding"
	"github.com/openconfig/ondatra/binding/grpcutil"
        "github.com/openconfig/ondatra/binding/introspect"

	opb "github.com/openconfig/ondatra/proto"
	"github.com/openconfig/ondatra/proxy"
	"github.com/sonic-net/sonic-mgmt/sdn_tests/pins_ondatra/infrastructure/binding/bindingbackend"

	gpb "github.com/openconfig/gnmi/proto/gnmi"

	rpb "github.com/openconfig/ondatra/proxy/proto/reservation"
	p4pb "github.com/p4lang/p4runtime/go/p4/v1"
)

var (
	supportedBackends = []string{"pins"}
	backendType       = flag.String("pins_backend_type", "pins", fmt.Sprintf("define the pins-ondatra backend type, choose from : %v. Uses pins as default.", supportedBackends))
)

var (
	// validate that the Binding fulfills both binding.Binding and proxy.Dialer
	// interfaces.
	_ binding.Binding = &Binding{}
	_ proxy.Dialer    = &Binding{}
)

// Binding is a binding for PINS switches.
type Binding struct {
	resv       *binding.Reservation
	httpDialer func(target string) (proxy.HTTPDoCloser, error)
        backend    bindingbackend.Backend
}

// Option are configurable inputs to the binding.
type Option func(b *Binding)

// WithHTTPDialer provides a custom http dialer that is capable of dialing specific targets.
func WithHTTPDialer(f func(target string) (proxy.HTTPDoCloser, error)) Option {
	return func(b *Binding) {
		b.httpDialer = f
	}
}

// WithBackend provides a custom backend to support different bindings.
func WithBackend(backend bindingbackend.Backend) Option {
	return func(b *Binding) {
		b.backend = backend
	}
}

// New returns a new instance of a PINS Binding.
func New() (binding.Binding, error) {
	return NewWithOpts()
}

type httpClient struct {
	*http.Client
}

func (h *httpClient) Close() error {
	return nil
}

func defaultHTTPDialer(target string) (proxy.HTTPDoCloser, error) {
	return &httpClient{http.DefaultClient}, nil
}

// createBackendFromFlag creates a backend based on the passed flag.
func createBackendFromFlag() (bindingbackend.Backend, error) {
	switch *backendType {
	case "pins":
                log.Infof("Creating PINS backend")
		return pinsbackend.New(), nil
	default:
		return nil, fmt.Errorf("unknown backend type: %q", *backendType)
	}
}

// NewWithOpts returns a new instance of a PINS Binding.
func NewWithOpts(opts ...Option) (*Binding, error) {
	b := &Binding{
		httpDialer: defaultHTTPDialer,
	}

	for _, opt := range opts {
		opt(b)
	}

        if b.backend != nil {
		return b, nil
	}

	backend, err := createBackendFromFlag()
	if err != nil {
		return nil, fmt.Errorf("createBackendFromFlag() failed, err : %v", err)
	}
	b.backend = backend

	return b, nil
}

// Reserve returns a testbed meeting requirements of testbed proto.
func (b *Binding) Reserve(ctx context.Context, tb *opb.Testbed, runtime, waitTime time.Duration, partial map[string]string) (*binding.Reservation, error) {
	if len(partial) > 0 {
		return nil, fmt.Errorf("PINSBind Reserve does not yet support partial mappings")
	}

	reservedtopology, err := b.backend.ReserveTopology(ctx, tb, runtime, waitTime)
	if err != nil {
		return nil, fmt.Errorf("failed to reserve topology: %v", err)
	}

	resv := &binding.Reservation{ID: reservedtopology.ID, DUTs: map[string]binding.DUT{}}
	for _, dut := range reservedtopology.DUTs {
		resv.DUTs[dut.ID] = &pinsDUT{
			AbstractDUT: &binding.AbstractDUT{&binding.Dims{
				Name:  dut.Name,
				Ports: dut.PortMap,
			}},
			bind: b,
			grpc: dut.GRPC,
		}
	}

	if len(reservedtopology.ATEs) != 0 {
		resv.ATEs = map[string]binding.ATE{}
	}
	for _, ate := range reservedtopology.ATEs {
		resv.ATEs[ate.ID] = &pinsATE{
			AbstractATE: &binding.AbstractATE{&binding.Dims{
				Name:  ate.Name,
				Ports: ate.PortMap,
			}},
			http: ate.HTTP,
		}
	}

	b.resv = resv
	return resv, nil
}

// Release returns the testbed to a pool of resources.
func (b *Binding) Release(ctx context.Context) error {
	return b.backend.Release(ctx)
}

type pinsDUT struct {
	*binding.AbstractDUT
	bind *Binding
	grpc bindingbackend.GRPCServices
}

type pinsATE struct {
	*binding.AbstractATE
	bind *Binding
	http bindingbackend.HTTPService
}

// DialGRPC will return a gRPC client conn for the target. This method should
// be used by any new service definitions which create underlying gRPC
// connections.
func (b *Binding) DialGRPC(ctx context.Context, addr string, opts ...grpc.DialOption) (*grpc.ClientConn, error) {
	return b.backend.DialGRPC(ctx, addr, opts...)
}

// HTTPClient returns a http client that is capable of dialing the provided target.
func (b *Binding) HTTPClient(target string) (proxy.HTTPDoCloser, error) {
	return b.httpDialer(target)
}

func (d *pinsDUT) dialGRPC(ctx context.Context, grpcInfo bindingbackend.ServiceInfo, opts ...grpc.DialOption) (*grpc.ClientConn, error) {
	addr := grpcInfo.Addr
	if addr == "" {
		return nil, fmt.Errorf("service not registered on DUT %q", d.Name())
	}

	timeout := grpcInfo.Timeout
	if timeout == 0 {
		timeout = 2 * time.Minute
	}

	ctx, cancel := grpcutil.WithDefaultTimeout(ctx, timeout)
	defer cancel()
	opts = append(opts,
		grpcutil.WithUnaryDefaultTimeout(timeout),
		grpcutil.WithStreamDefaultTimeout(timeout),
		grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(1024*1024*20)))

	return d.bind.DialGRPC(ctx, addr, opts...)
}

// DialGNMI connects directly to the switch's proxy.
func (d *pinsDUT) DialGNMI(ctx context.Context, opts ...grpc.DialOption) (gpb.GNMIClient, error) {
	conn, err := d.dialGRPC(ctx, d.grpc.Info[introspect.GNMI], opts...)
	if err != nil {
		return nil, fmt.Errorf("dialGRPC() for GNMI failed, err : %v", err)
	}

	cli, err := d.bind.backend.GNMIClient(ctx, d.AbstractDUT, conn)
	if err != nil {
		return nil, err
	}

        log.InfoContextf(ctx, "GNMI dial success Address:%s, Switch:%s", conn.Target(), d.Name())
	return &clientWrap{GNMIClient: cli}, nil
}

type clientWrap struct {
	gpb.GNMIClient
}

// wrapValueInUpdate wraps the typed value in the provided update into a
// serialized JSON node., e.g.
// - 123 -> {"foo": 123}
// - [{"str": "one"}] -> {"foo": [{"str": "one"}]}
// - {"str": "test-string"} -> {"foo": {"str": "test-string"}}
func wrapValueInUpdate(up *gpb.Update) error {
	elems := up.GetPath().GetElem()
	if len(elems) == 0 {
		// root path case
		return nil
	}
	name := elems[len(elems)-1].GetName()
	var i any
	if err := json.Unmarshal(up.GetVal().GetJsonIetfVal(), &i); err != nil {
		return fmt.Errorf("unable to unmarshal config: %v", err)
	}

	// For list paths such as /interfaces/interface[name=<key>], JSON IETF value
	// needs to be an array instead of an object. Ondatra returns value for such paths
	// as an object, which need to be translated into a JSON array. E.g.
	// - {"str": "test-string"} -> [{"str": "test-string"}]
	if len(elems[len(elems)-1].GetKey()) > 0 {
		// The path is a list node. Perform translation to JSON array.
		var arr []any
		arr = append(arr, i)
		arrVal, err := json.Marshal(arr)
		if err != nil {
			return fmt.Errorf("unable to marshal value %v as a JSON array: %v", arr, err)
		}
		if err := json.Unmarshal(arrVal, &i); err != nil {
			return fmt.Errorf("unable to unmarshal JSON array config: %v", err)
		}
	}
	js, err := json.MarshalIndent(map[string]any{name: i}, "", "  ")
	if err != nil {
		return fmt.Errorf("unable to marshal config with wrapping container: %v", err)
	}
	up.GetVal().Value = &gpb.TypedValue_JsonIetfVal{js}
	return nil
}

func (c *clientWrap) Set(ctx context.Context, in *gpb.SetRequest, opts ...grpc.CallOption) (*gpb.SetResponse, error) {
	for _, up := range in.GetReplace() {
		if err := wrapValueInUpdate(up); err != nil {
			return nil, err
		}
	}
	for _, up := range in.GetUpdate() {
		if err := wrapValueInUpdate(up); err != nil {
			return nil, err
		}
	}

	return c.GNMIClient.Set(ctx, in, opts...)
}

func (c *clientWrap) Get(ctx context.Context, in *gpb.GetRequest, opts ...grpc.CallOption) (*gpb.GetResponse, error) {
	return c.GNMIClient.Get(ctx, in, opts...)
}

type subscribeClientWrap struct {
	gpb.GNMI_SubscribeClient
	client *clientWrap
}

// CloseSend signals that the client has done sending messages to the server.
// Calling the CloseSend will cause PINs to close the Subscribe stream and return an
// error. Hence we overwrite this method to be no-op here.
func (sc *subscribeClientWrap) CloseSend() error {
	return nil
}

func (c *clientWrap) Subscribe(ctx context.Context, opts ...grpc.CallOption) (gpb.GNMI_SubscribeClient, error) {
	sub, err := c.GNMIClient.Subscribe(ctx, opts...)
	if err != nil {
		return nil, err
	}
	return &subscribeClientWrap{GNMI_SubscribeClient: sub, client: c}, nil
}

func (c *clientWrap) Capabilities(ctx context.Context, in *gpb.CapabilityRequest, opts ...grpc.CallOption) (*gpb.CapabilityResponse, error) {
	return c.GNMIClient.Capabilities(ctx, in, opts...)
}

// DialGNOI connects directly to the switch's proxy.
func (d *pinsDUT) DialGNOI(ctx context.Context, opts ...grpc.DialOption) (gnoigo.Clients, error) {
	conn, err := d.dialGRPC(ctx, d.grpc.Info[introspect.GNOI], opts...)
	if err != nil {
		return nil, fmt.Errorf("dialGRPC() for GNOI failed, err : %v", err)
	}

	log.InfoContextf(ctx, "GNOI dial success Address:%s, Switch:%s", conn.Target(), d.Name())
	return &GNOIClients{
		Clients: gnoigo.NewClients(conn),
	}, nil
}

// GNOIClients consist of the GNOI clients supported by PINs.
type GNOIClients struct {
	gnoigo.Clients
}

// DialP4RT connects directly to the switch's proxy.
func (d *pinsDUT) DialP4RT(ctx context.Context, opts ...grpc.DialOption) (p4pb.P4RuntimeClient, error) {
	conn, err := d.dialGRPC(ctx, d.grpc.Info[introspect.P4RT], opts...)
	if err != nil {
		return nil, fmt.Errorf("dialGRPC() for P4RT failed, err : %v", err)
	}

	log.InfoContextf(ctx, "P4RT dial success Address:%s, Switch:%s", conn.Target(), d.Name())
	return p4pb.NewP4RuntimeClient(conn), nil
}

// DialConsole returns a StreamClient for the DUT.
func (d *pinsDUT) DialConsole(ctx context.Context) (binding.ConsoleClient, error) {
	return d.bind.backend.DialConsole(ctx, d.AbstractDUT)
}

// FetchReservation unimplemented for experimental purposes.
func (*Binding) FetchReservation(context.Context, string) (*binding.Reservation, error) {
	return nil, nil
}

// Resolve will return a concrete reservation with services defined.
func (b *Binding) Resolve() (*rpb.Reservation, error) {
	devices := map[string]*rpb.ResolvedDevice{}
	for k, d := range b.resv.DUTs {
		rD, err := b.resolveDUT(k, d.(*pinsDUT))
		if err != nil {
			return nil, err
		}
		devices[k] = rD
	}
	ates := map[string]*rpb.ResolvedDevice{}
	for k, a := range b.resv.ATEs {
		rD, err := b.resolveATE(k, a.(*pinsATE))
		if err != nil {
			return nil, err
		}
		ates[k] = rD
	}
	return &rpb.Reservation{
		Id:      b.resv.ID,
		Ates:    ates,
		Devices: devices,
	}, nil
}

func resolvePort(k string, p *binding.Port) *rpb.ResolvedPort {
	return &rpb.ResolvedPort{
		Id:    k,
		Speed: p.Speed,
		Name:  p.Name,
	}
}

func (b *Binding) resolveDUT(key string, d *pinsDUT) (*rpb.ResolvedDevice, error) {
	ports := map[string]*rpb.ResolvedPort{}
	for k, p := range d.Ports() {
		ports[k] = resolvePort(k, p)
	}
	services := map[string]*rpb.Service{
		"gnmi.gNMI": {
			Id: "gnmi.gNMI",
			Endpoint: &rpb.Service_ProxiedGrpc{
				ProxiedGrpc: &rpb.ProxiedGRPCEndpoint{
					Address: d.grpc.Info[introspect.GNMI].Addr,
					Proxy:   nil,
				},
			},
		},
		"p4.v1.P4Runtime": {
			Id: "p4.v1.P4Runtime",
			Endpoint: &rpb.Service_ProxiedGrpc{
				ProxiedGrpc: &rpb.ProxiedGRPCEndpoint{
					Address: d.grpc.Info[introspect.P4RT].Addr,
					Proxy:   nil,
				},
			},
		},
	}
	return &rpb.ResolvedDevice{
		Id:              key,
		HardwareModel:   d.HardwareModel(),
		Vendor:          d.Vendor(),
		SoftwareVersion: d.SoftwareVersion(),
		Name:            d.Name(),
		Ports:           ports,
		Services:        services,
	}, nil
}

func (b *Binding) resolveATE(key string, d *pinsATE) (*rpb.ResolvedDevice, error) {
	ports := map[string]*rpb.ResolvedPort{}
	for k, p := range d.Ports() {
		ports[k] = resolvePort(k, p)
	}
	services := map[string]*rpb.Service{
		"http": {
			Id: "http",
			Endpoint: &rpb.Service_HttpOverGrpc{
				HttpOverGrpc: &rpb.HTTPOverGRPCEndpoint{
					Address: d.http.Addr,
				},
			},
		},
	}
	return &rpb.ResolvedDevice{
		Id:              key,
		HardwareModel:   d.HardwareModel(),
		Vendor:          d.Vendor(),
		SoftwareVersion: d.SoftwareVersion(),
		Name:            d.Name(),
		Ports:           ports,
		Services:        services,
	}, nil
}
