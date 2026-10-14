(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x402 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv16 32) (_ bv31 32)))))))
(let ((?x1183 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x898 (bvshl (bvsub independent_opaque_0 independent_opaque_1) ?x1183)))
(and (distinct ?x898 ?x402) true)))))
(check-sat)
