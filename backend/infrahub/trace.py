import os
from typing import TYPE_CHECKING, Any, Dict, List

from opentelemetry import context, trace
from opentelemetry.trace import StatusCode
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPSpanExporter

from pydantic import parse_obj_as

from infrahub import __version__

INFRAHUB_OTLP_EXPORTER = os.environ.get("INFRAHUB_OTLP_EXPORTER", "otlp")
INFRAHUB_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")
INFRAHUB_OTLP_PROTOCOL = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "grpc")

def get_tracer(name: str = "infrahub") -> trace.Tracer:
    return trace.get_tracer(name)

def get_current_span_with_context() -> trace.Span:
    return trace.get_current_span()

def get_traceid() -> str:
    current_span = get_current_span_with_context()
    trace_id = current_span.get_span_context().trace_id
    if trace_id == 0:
        return None
    return hex(trace_id)

def set_span_status(status_code: int) -> None:
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        status = StatusCode(status_code)
        current_span().set_attribute("status_code", status)

def set_span_data(key: str, value: str) -> None:
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        current_span().set_attribute(key, value)

def add_span_event(event_name: str, event_attributes: dict) -> None:
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        current_span.add_event(event_name, event_attributes)

def add_span_exception(exception: Exception) -> None:
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        current_span.record_exception(exception)

def create_tracer_provider(version: str, exporter_type: str, endpoint: str = None, protocol: str = None) -> TracerProvider:
    # Create a BatchSpanProcessor exporter based on the type
    if exporter_type == "console":
        exporter = ConsoleSpanExporter()
    elif exporter_type == "otlp":
        if protocol == "http/protobuf":
            exporter = HTTPSpanExporter(endpoint=endpoint+"/v1/traces")
        elif protocol == "grpc":
            exporter = GRPCSpanExporter(endpoint=endpoint)
    else:
        ## TODO zipkin and none
        raise ValueError("Exporter type unsupported by Infrahub")

    # Resource can be required for some backends, e.g. Jaeger
    resource = Resource(attributes={
        "service.name": "infrahub",
        "service.version": version
    })
    span_processor = BatchSpanProcessor(exporter)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(span_processor)

    return tracer_provider

# Create a trace provider with the exporter
tracer_provider = create_tracer_provider(version=__version__, exporter_type=INFRAHUB_OTLP_EXPORTER, endpoint=INFRAHUB_OTLP_ENDPOINT, protocol=INFRAHUB_OTLP_PROTOCOL)
tracer_provider.get_tracer(__name__)

# Register the trace provider
trace.set_tracer_provider(tracer_provider)
