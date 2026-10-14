(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x42 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x67 (bvadd independent_opaque_0 ?x42)))
(let ((?x428 (bvadd ?x42 independent_opaque_0)))
(and (distinct ?x428 ?x67) true)))))
(check-sat)
