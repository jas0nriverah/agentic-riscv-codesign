(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x10 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (_ bv4294770688 32))))
(let ((?x996 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x392 (bvshl (bvadd independent_opaque_0 (_ bv4294967293 32)) ?x996)))
(and (distinct ?x392 ?x10) true)))))
(check-sat)
