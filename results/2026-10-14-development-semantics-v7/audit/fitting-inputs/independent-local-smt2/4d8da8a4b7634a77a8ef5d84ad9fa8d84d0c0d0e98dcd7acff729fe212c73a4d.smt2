(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x996 (bvadd independent_opaque_0 (_ bv21 32))))
(let ((?x1104 (bvadd (bvshl independent_opaque_0 (bvand (_ bv0 32) (_ bv31 32))) (_ bv21 32))))
(and (distinct ?x1104 ?x996) true))))
(check-sat)
