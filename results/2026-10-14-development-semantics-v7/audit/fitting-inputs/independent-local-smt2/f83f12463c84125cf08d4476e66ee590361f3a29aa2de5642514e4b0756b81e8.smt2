(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1103 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (_ bv4 32))))
(let ((?x573 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x24 (bvshl (bvadd independent_opaque_0 (_ bv1 32)) ?x573)))
(and (distinct ?x24 ?x1103) true)))))
(check-sat)
