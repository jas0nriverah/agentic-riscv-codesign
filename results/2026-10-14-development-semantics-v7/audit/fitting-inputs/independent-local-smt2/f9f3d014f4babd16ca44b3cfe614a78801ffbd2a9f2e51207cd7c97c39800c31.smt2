(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(assert
 (let ((?x941 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (_ bv2047 32))))
(let ((?x624 (bvsub (bvadd (bvsub independent_opaque_1 independent_opaque_0) (_ bv2047 32)) independent_opaque_1)))
(and (distinct ?x624 ?x941) true))))
(check-sat)
